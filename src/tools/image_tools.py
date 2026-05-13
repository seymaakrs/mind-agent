from agents import FunctionTool, function_tool

from src.app.config import get_settings, AgentInstructionConfig
from src.infra.errors import classify_error
from src.infra.firebase_client import get_storage_client, save_media_record, save_dry_run_log
from src.infra.google_ai_client import get_image_generation_client
from src.models.prompts import ImagePrompt, build_image_prompt_model


# Tool-level retry for transient image generation failures.
# Brand-aware path occasionally hits 5xx / empty responses from Gemini;
# agents see generic errors and give up. Retrying inside the tool keeps
# the agent layer clean.
import asyncio
import logging

_log = logging.getLogger(__name__)

# Delays between attempts (seconds). attempt 0 = immediate;
# attempt 1 = wait 5s; attempt 2 = wait 15s.
_RETRY_DELAYS: list[int] = [0, 5, 15]

# Error codes that should NOT trigger a retry — they won't fix themselves.
_NON_RETRYABLE_CODES = frozenset({
    "CONTENT_POLICY",
    "INVALID_INPUT",
    "AUTH_ERROR",
    "PERMISSION_DENIED",
    "INSUFFICIENT_BALANCE",
    "NOT_FOUND",
})


async def _generate_with_retry(
    image_client,
    prompt: str,
    aspect_ratio: str = "4:5",
    max_retries: int = 2,
    delays: list[int] | None = None,
):
    """Call image_client.generate_image with automatic retry on transient
    failures.

    Retries on: RATE_LIMIT (429), SERVER_ERROR (5xx), TIMEOUT, NETWORK_ERROR,
    or empty response (treated as transient).

    Does NOT retry on: CONTENT_POLICY, INVALID_INPUT, AUTH_ERROR,
    PERMISSION_DENIED, INSUFFICIENT_BALANCE, NOT_FOUND.

    Args:
        image_client: Has async generate_image(prompt, aspect_ratio) method.
        prompt: Full prompt string.
        aspect_ratio: Image aspect ratio.
        max_retries: Maximum retry attempts (initial call + retries).
        delays: Per-attempt sleep durations. Defaults to _RETRY_DELAYS.

    Returns:
        list of image bytes (non-empty) on success.

    Raises:
        The last exception encountered if all retries exhaust, or the
        first non-retryable exception immediately.
    """
    delays = delays if delays is not None else _RETRY_DELAYS
    attempts = max_retries + 1
    last_exc: Exception | None = None

    for attempt in range(attempts):
        # Sleep before retry (skip on first attempt)
        if attempt > 0 and attempt - 1 < len(delays):
            wait = delays[attempt - 1] if attempt - 1 < len(delays) else delays[-1]
            if wait > 0:
                _log.warning(
                    "image_generate retry %d/%d after %ds — last: %s",
                    attempt, max_retries, wait, last_exc,
                )
                await asyncio.sleep(wait)

        try:
            images = await image_client.generate_image(
                prompt=prompt, aspect_ratio=aspect_ratio,
            )
            if images:
                return images
            # Empty response — treat as transient
            last_exc = RuntimeError("Image API returned empty response")
            _log.warning("image_generate: empty response on attempt %d", attempt + 1)
            continue
        except Exception as exc:
            last_exc = exc
            # Classify to decide whether to retry
            classified = classify_error(exc, "google_ai")
            code = str(classified.get("error_code") or "")
            if code in _NON_RETRYABLE_CODES:
                _log.error(
                    "image_generate non-retryable (%s): %s",
                    code, exc,
                )
                raise

    # All retries exhausted
    assert last_exc is not None
    _log.error("image_generate exhausted %d retries: %s", max_retries, last_exc)
    raise last_exc


def _count_tokens(text: str) -> int:
    """Tahmini token sayisini hesaplar (tiktoken cl100k_base encoding)."""
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        # tiktoken yoksa basit tahmin: ~4 karakter = 1 token
        return len(text) // 4




_GENERATE_IMAGE_DESCRIPTION = (
    "Generates or edits images based on structured prompt data. This is the ONLY tool for image tasks. "
    "\n\n"
    "INPUT - prompt_data (ImagePrompt): You MUST provide ALL required fields: "
    "- scene: Main scene description (2-3 sentences) "
    "- subject: Primary subject/focal point "
    "- style: Artistic style (e.g., 'minimalist flat design', 'photorealistic') "
    "- colors: List of dominant colors (use brand colors, be specific like '#FF5733') "
    "- mood: Emotional atmosphere (e.g., 'professional and calm') "
    "- composition: Visual arrangement (e.g., 'rule of thirds', 'centered') "
    "- lighting: Lighting setup (e.g., 'soft natural daylight', 'dramatic rim lighting') "
    "- background: Background details "
    "- text_elements: (optional) Text to include "
    "- additional_details: (optional) Extra effects or requirements "
    "\n\n"
    "business_id: REQUIRED if available in context. The business ID for organizing files. "
    "\n\n"
    "WHEN TO USE source_file_path: "
    "If the task mentions using an existing image (logo, asset) - provide the Firebase Storage path. "
    "Keywords: 'use logo', 'place logo', 'include logo', 'combine with', 'overlay'. "
    "\n\n"
    "WHEN TO LEAVE source_file_path EMPTY: "
    "If creating a completely NEW image from scratch without referencing existing images."
    "\n\n"
    "aspect_ratio: Image aspect ratio. Options: '4:5' (Instagram feed portrait — RECOMMENDED), '1:1' (square), '16:9' (widescreen), '9:16' (portrait/story), '4:3'. Default: '4:5'. "
    "WARNING: '3:4' is NOT valid for Instagram feed posts (ratio 0.75 < min 0.8). Always use '4:5' for Instagram."
)


def _make_generate_image_tool(prompt_model: type[ImagePrompt]) -> FunctionTool:
    """Factory: Dynamic ImagePrompt tipi ile generate_image FunctionTool olusturur."""

    @function_tool(
        name_override="generate_image",
        description_override=_GENERATE_IMAGE_DESCRIPTION,
        strict_mode=False,
    )
    async def generate_image(
        prompt_data: prompt_model,
        file_name: str,
        business_id: str | None = None,
        source_file_path: str | None = None,
        aspect_ratio: str = "4:5",
    ) -> dict[str, str | bool]:
        """
        Generate a new image or edit/combine with an existing image.

        Args:
            prompt_data: Structured ImagePrompt with all visual details.
            file_name: Name to save the generated image as in Firebase Storage.
            business_id: Business ID for organizing files under business/{id}/images/.
            source_file_path: Optional. Firebase Storage path of source image to use (e.g., logo).
                              If provided, the image will be edited/combined with this source.
                              If None, a completely new image will be generated.
            aspect_ratio: Image aspect ratio ("4:5", "1:1", "16:9", "9:16", "4:3"). Default is "4:5". Do NOT use "3:4" for Instagram.
        """
        settings = get_settings()

        # Convert structured prompt to string
        prompt = prompt_data.to_prompt_string()

        # DRY-RUN MODE: Log prompt without calling Google API
        if settings.dry_run:
            token_count = _count_tokens(prompt)
            print(f"[DRY-RUN] Image prompt token count: {token_count}")
            print(f"[DRY-RUN] Full prompt:\n{prompt[:500]}...")

            # Save to Firestore for analysis
            if business_id:
                try:
                    save_dry_run_log(
                        business_id=business_id,
                        media_type="image",
                        prompt_data=prompt_data.model_dump(),
                        full_prompt=prompt,
                        token_count=token_count,
                        file_name=file_name,
                        aspect_ratio=aspect_ratio,
                    )
                except Exception as e:
                    print(f"[DRY-RUN] Firestore log hatasi: {e}")

            return {
                "success": True,
                "message": f"[DRY-RUN] Gorsel uretimi simule edildi. Token sayisi: {token_count}",
                "path": f"[DRY-RUN] images/{business_id or 'unknown'}/{file_name}",
                "public_url": "[DRY-RUN] No actual image generated",
                "fileName": file_name,
                "dry_run": True,
                "token_count": token_count,
            }

        # NORMAL MODE: Call Google API
        image_client = get_image_generation_client()
        storage_client = get_storage_client()

        try:
            if source_file_path:
                # Edit/combine mode - use existing image as source
                source_image = storage_client.download_file(source_file_path)
                images = await image_client.edit_image(
                    prompt=prompt,
                    source_image=source_image,
                    aspect_ratio=aspect_ratio,
                )
                message = "Gorsel duzenlendi ve kaydedildi"
            else:
                # Generate mode - create new image from scratch.
                # Use retry helper to survive transient Gemini failures.
                images = await _generate_with_retry(
                    image_client=image_client,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                )
                message = "Gorsel olusturuldu"

            if not images:
                # Retry helper raises on exhaustion, so this is defensive.
                return {"success": False, "error": "Gorsel uretilemedi."}

            # Upload first image to Firebase Storage
            image_data = images[0]
            if business_id:
                destination_path = f"images/{business_id}/{file_name}"
            else:
                destination_path = f"images/{file_name}"
            upload_result = storage_client.upload_file(
                file_data=image_data,
                destination_path=destination_path,
                content_type="image/png",
            )

            # Media kaydini Firestore'a yaz (business_id varsa)
            if business_id:
                try:
                    save_media_record(
                        business_id=business_id,
                        media_type="image",
                        storage_path=upload_result["path"],
                        public_url=upload_result["public_url"],
                        file_name=file_name,
                        prompt_summary=prompt_data.scene[:200] if prompt_data.scene else None,
                    )
                except Exception:
                    pass  # Media kaydi basarisiz olsa bile ana islem basarili

            return {
                "success": True,
                "message": message,
                "path": upload_result["path"],
                "public_url": upload_result["public_url"],
                "fileName": file_name,
            }

        except Exception as exc:
            return classify_error(exc, "google_ai")

    return generate_image


# Default tool instance (backward compatibility)
generate_image = _make_generate_image_tool(ImagePrompt)


def get_image_tools(config: AgentInstructionConfig | None = None) -> list[FunctionTool]:
    """
    Image agent icin kullanilabilir tool listesi.

    Config verilirse dynamic ImagePrompt modeli ile tool olusturur.
    Config yoksa default (hardcoded) ImagePrompt kullanir.
    """
    if config and config.prompt_fields:
        prompt_model = build_image_prompt_model(config)
        return [_make_generate_image_tool(prompt_model)]
    return [generate_image]


__all__ = ["generate_image", "get_image_tools"]
