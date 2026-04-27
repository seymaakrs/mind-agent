from typing import Any

from agents import FunctionTool, function_tool

from src.app.config import get_settings, AgentInstructionConfig
from src.infra.errors import classify_error
from src.infra.firebase_client import get_storage_client, save_media_record, save_dry_run_log
from src.infra.google_ai_client import get_image_generation_client
from src.infra.path_safety import safe_path_segment
from src.models.prompts import ImagePrompt, build_image_prompt_model


def _validate_image_path_inputs(
    *,
    file_name: str,
    business_id: str | None,
    source_file_path: str | None,
) -> dict[str, Any] | None:
    """
    file_name, business_id, source_file_path uzerinde path-traversal kontrolu.

    Storage backend (Firebase Storage / GCS) nesne deposu olsa da '../' iceren
    bir nesne yolu, baska bir business'in verisinin uzerine yazilmasina yol acar.
    Bu nedenle her segment alfanumerik+dot+dash+underscore'la sinirli, '..'
    icermez. source_file_path multi-segment olabilir; her '/'-ayrik segment
    ayri ayri dogrulanir.

    Returns:
        dict (success=False, error_code=INVALID_INPUT) — gecersizse.
        None — gecerliyse, caller normal akista devam eder.
    """
    try:
        safe_path_segment(file_name)
    except ValueError as exc:
        return {
            "success": False,
            "error": f"Invalid file_name: {exc}",
            "error_code": "INVALID_INPUT",
            "service": "image_tools",
            "retryable": False,
            "user_message_tr": (
                "Dosya adi gecersiz karakter iceriyor. Sadece harf, rakam, "
                "nokta, tire ve alt cizgi kullanilabilir."
            ),
        }

    if business_id is not None:
        try:
            safe_path_segment(business_id)
        except ValueError as exc:
            return {
                "success": False,
                "error": f"Invalid business_id: {exc}",
                "error_code": "INVALID_INPUT",
                "service": "image_tools",
                "retryable": False,
                "user_message_tr": "Business ID gecersiz karakter iceriyor.",
            }

    if source_file_path is not None:
        # Multi-segment path: her bilesen ayri dogrulanir.
        if source_file_path.startswith("/") or "\\" in source_file_path:
            return {
                "success": False,
                "error": (
                    f"Invalid source_file_path: absolute or backslash paths "
                    f"not allowed: {source_file_path!r}"
                ),
                "error_code": "INVALID_INPUT",
                "service": "image_tools",
                "retryable": False,
                "user_message_tr": "Kaynak dosya yolu gecerli formatta degil.",
            }
        for segment in source_file_path.split("/"):
            if not segment:
                # Cift slash veya bos segment — meşru bir storage path'inde olmaz
                return {
                    "success": False,
                    "error": (
                        f"Invalid source_file_path: empty segment in "
                        f"{source_file_path!r}"
                    ),
                    "error_code": "INVALID_INPUT",
                    "service": "image_tools",
                    "retryable": False,
                    "user_message_tr": "Kaynak dosya yolu gecerli formatta degil.",
                }
            try:
                safe_path_segment(segment)
            except ValueError as exc:
                return {
                    "success": False,
                    "error": f"Invalid source_file_path segment: {exc}",
                    "error_code": "INVALID_INPUT",
                    "service": "image_tools",
                    "retryable": False,
                    "user_message_tr": "Kaynak dosya yolu gecerli formatta degil.",
                }
    return None


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
        # Path-traversal koruma (SECURITY_REPORT_TR.md Madde 6).
        # Storage cagrilmadan onceki son savunma katmani.
        path_error = _validate_image_path_inputs(
            file_name=file_name,
            business_id=business_id,
            source_file_path=source_file_path,
        )
        if path_error is not None:
            return path_error

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
                # Generate mode - create new image from scratch
                images = await image_client.generate_image(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                )
                message = "Gorsel olusturuldu"

            if not images:
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
