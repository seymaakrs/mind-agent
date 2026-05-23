"""Image generation backend factory — picks Gemini or OpenAI by model name.

Backend-agnostic interface (matches `ImageGenerationClient` shape):
    async def generate_image(prompt: str, aspect_ratio: str) -> list[bytes]
    async def edit_image(prompt, source_image: bytes, aspect_ratio) -> list[bytes]

Routing rule:
    image_generation_model startswith "gpt-image" -> OpenAI client
    otherwise                                     -> legacy Gemini client

Default is now OpenAI gpt-image-2 (high quality) as configured in
src/app/config.py ModelSettings.image_generation_model. Override via
Firestore settings/app_settings.imageGenerationModel.
"""
from __future__ import annotations

from src.app.config import get_model_settings


def get_image_client():
    """Return the active image generation client based on model setting."""
    ms = get_model_settings()
    model = (getattr(ms, "image_generation_model", "") or "").lower()

    if model.startswith("gpt-image"):
        from src.infra.openai_image_client import OpenAIImageClient
        return OpenAIImageClient()

    # Fallback to legacy Gemini client
    from src.infra.google_ai_client import get_image_generation_client
    return get_image_generation_client()


__all__ = ["get_image_client"]
