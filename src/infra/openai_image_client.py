"""OpenAI gpt-image-2 image generation client.

GPT Image 2, OpenAI'in 2026 flagship gorsel modelidir; Gemini 2.5 Flash
Image'in yerini aldi. Yuksek kaliteli, prompt-adherent, photorealistic
ciktilar uretiyor.

Endpoint:
    POST https://api.openai.com/v1/images/generations    (generate)
    POST https://api.openai.com/v1/images/edits          (edit)

Default config:
    model:   gpt-image-2   (Firestore settings/app_settings.imageGenerationModel override eder)
    quality: high          (Firestore .imageGenerationQuality override eder)

Aspect ratio mapping — OpenAI gpt-image yalnizca 3 size kabul eder
(1024x1024 / 1024x1536 / 1536x1024). Diger oranlar en yakin'a yuvarlanir.

Maliyet (high quality, May 2026 fiyat):
    1024x1024:  $0.211/image
    1024x1536:  $0.165/image
    1536x1024:  $0.165/image
"""
from __future__ import annotations

import base64
from typing import Literal

import httpx

from src.app.config import get_settings, get_model_settings
from src.infra.errors import ServiceError


# Aspect ratio -> OpenAI size mapping (yalnizca 3 size desteklenir)
# 4:5, 9:16, 3:4 ve 2:3 portrait -> 1024x1536
# 16:9, 4:3, 3:2 landscape -> 1536x1024
# 1:1 square -> 1024x1024
_ASPECT_TO_SIZE: dict[str, str] = {
    "1:1": "1024x1024",
    "4:5": "1024x1536",   # Instagram feed portrait (en yakin)
    "2:3": "1024x1536",
    "3:4": "1024x1536",
    "9:16": "1024x1536",  # Stories / Reels
    "4:3": "1536x1024",
    "3:2": "1536x1024",
    "16:9": "1536x1024",  # Widescreen / YouTube thumbnail
}


QualityLevel = Literal["low", "medium", "high"]


class OpenAIImageClient:
    """OpenAI gpt-image-2 client. Drop-in replacement for ImageGenerationClient."""

    BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-image-2"
    DEFAULT_QUALITY: QualityLevel = "high"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY env degiskeni ayarlanmamis")

    @property
    def _api_key(self) -> str:
        return self._settings.openai_api_key

    @property
    def _model(self) -> str:
        ms = get_model_settings()
        return getattr(ms, "image_generation_model", None) or self.DEFAULT_MODEL

    @property
    def _quality(self) -> QualityLevel:
        ms = get_model_settings()
        raw = getattr(ms, "image_generation_quality", None) or self.DEFAULT_QUALITY
        if raw not in ("low", "medium", "high"):
            return self.DEFAULT_QUALITY
        return raw  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_size(aspect_ratio: str) -> str:
        return _ASPECT_TO_SIZE.get(aspect_ratio, "1024x1024")

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "4:5",
    ) -> list[bytes]:
        """Text-to-image. Returns list of PNG bytes."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "size": self._resolve_size(aspect_ratio),
            "quality": self._quality,
            "n": 1,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/generations",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code != 200:
                raise ServiceError(
                    f"OpenAI image API {response.status_code}: {response.text[:500]}",
                    status_code=response.status_code,
                    service="openai",
                )
            data = response.json()

        return self._extract_images(data)

    async def edit_image(
        self,
        prompt: str,
        source_image: bytes,
        aspect_ratio: str = "4:5",
    ) -> list[bytes]:
        """Edit / combine with an existing image (multipart upload)."""
        # /v1/images/edits is multipart/form-data, not JSON.
        size = self._resolve_size(aspect_ratio)
        files = {
            "image": ("source.png", source_image, "image/png"),
        }
        form = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "quality": self._quality,
            "n": "1",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}  # no Content-Type for multipart

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/images/edits",
                headers=headers,
                data=form,
                files=files,
            )
            if response.status_code != 200:
                raise ServiceError(
                    f"OpenAI image edit API {response.status_code}: {response.text[:500]}",
                    status_code=response.status_code,
                    service="openai",
                )
            data = response.json()

        return self._extract_images(data)

    @staticmethod
    def _extract_images(response_data: dict) -> list[bytes]:
        """Decode b64_json fields from response.data list."""
        out: list[bytes] = []
        for item in response_data.get("data", []) or []:
            b64 = item.get("b64_json")
            if b64:
                out.append(base64.b64decode(b64))
        return out


__all__ = ["OpenAIImageClient", "QualityLevel"]
