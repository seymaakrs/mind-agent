"""OpenAI image generation client (gpt-image-1 / DALL-E 3).

Drop-in replacement for ImageGenerationClient (Gemini). Same async
interface — `generate_image(prompt, aspect_ratio) -> list[bytes]` —
so existing tools/retry helper work unchanged.

Toggle via Firestore `settings/app_settings.imageGenerationModel`:
  - "gpt-image-1"  → this client
  - "dall-e-3"     → this client
  - "gemini-..."   → Gemini ImageGenerationClient

gpt-image-1 sizes are fixed: 1024x1024, 1024x1536, 1536x1024.
"""
from __future__ import annotations

import base64

from openai import AsyncOpenAI

from src.app.config import get_settings, get_model_settings
from src.infra.errors import ServiceError


DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"


def _aspect_to_size(aspect_ratio: str) -> str:
    """Map aspect ratio string to one of gpt-image-1's three supported sizes."""
    ar = (aspect_ratio or "").strip().lower()
    if ar == "1:1":
        return "1024x1024"
    if ar in {"16:9", "3:2", "4:3"}:
        return "1536x1024"
    # 4:5, 9:16, 2:3, unknown → Instagram-friendly portrait
    return "1024x1536"


def _get_async_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client. Module-level seam for tests to patch."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY env degiskeni ayarlanmamis")
    return AsyncOpenAI(api_key=settings.openai_api_key)


class OpenAIImageClient:
    """Image generation client using OpenAI's gpt-image-1 / DALL-E 3."""

    @property
    def _model(self) -> str:
        ms = get_model_settings()
        configured = ms.image_generation_model or DEFAULT_OPENAI_IMAGE_MODEL
        # Defensive: if admin sets a Gemini model here, fall back safely.
        if not (configured.startswith("gpt-image") or configured.startswith("dall-e")):
            return DEFAULT_OPENAI_IMAGE_MODEL
        return configured

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "4:5",
    ) -> list[bytes]:
        """Text-to-image generation via OpenAI Images API.

        Returns a list of raw image bytes (PNG). gpt-image-1 returns one
        image per call; list shape preserved for compatibility with the
        Gemini client.
        """
        size = _aspect_to_size(aspect_ratio)
        client = _get_async_client()

        try:
            response = await client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            raise ServiceError(
                f"OpenAI image API error: {exc}",
                status_code=status,
                service="openai_image",
            ) from exc

        images: list[bytes] = []
        for item in (response.data or []):
            b64 = getattr(item, "b64_json", None)
            if not b64:
                continue
            images.append(base64.b64decode(b64))
        return images

    async def edit_image(
        self,
        prompt: str,
        source_image: bytes,
        aspect_ratio: str = "4:5",
    ) -> list[bytes]:
        """Edit an existing image with a prompt (no mask = uses image as seed).

        Mask-based inpainting can be added later if needed.
        """
        size = _aspect_to_size(aspect_ratio)
        client = _get_async_client()

        try:
            response = await client.images.edit(
                model=self._model,
                image=source_image,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            raise ServiceError(
                f"OpenAI image edit error: {exc}",
                status_code=status,
                service="openai_image",
            ) from exc

        images: list[bytes] = []
        for item in (response.data or []):
            b64 = getattr(item, "b64_json", None)
            if not b64:
                continue
            images.append(base64.b64decode(b64))
        return images


__all__ = [
    "OpenAIImageClient",
    "DEFAULT_OPENAI_IMAGE_MODEL",
    "_aspect_to_size",
    "_get_async_client",
]
