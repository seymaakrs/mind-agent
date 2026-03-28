from __future__ import annotations

import asyncio
import time
from functools import lru_cache

import httpx
import jwt

from src.app.config import get_settings, get_model_settings


class KlingVideoClient:
    """Kling AI REST API video generation client.

    Supports text-to-video and image-to-video via Kling 3.0 API.
    Uses JWT (HS256) authentication with Access Key / Secret Key pair.

    API Docs: https://app.klingai.com/global/dev/document-api
    """

    BASE_URL = "https://api.klingai.com"
    DEFAULT_MODEL = "kling-v3"
    POLL_INTERVAL = 30  # seconds (Kling recommendation)
    MAX_POLL_ATTEMPTS = 20  # 10 minutes max wait
    JWT_TTL = 1800  # 30 minutes

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.kling_access_key or not self._settings.kling_secret_key:
            raise ValueError(
                "KLING_ACCESS_KEY ve KLING_SECRET_KEY env degiskenleri ayarlanmamis. "
                "API key'leri app.klingai.com/global/dev/api-key adresinden alinabilir."
            )

    @property
    def _model(self) -> str:
        model_settings = get_model_settings()
        return model_settings.kling_video_model or self.DEFAULT_MODEL

    def _generate_jwt(self) -> str:
        """Kling API icin JWT token uretir (HS256, 30dk TTL).

        Kling, standart API key yerine JWT tabanlı auth kullanır.
        Access Key (AK) token'ın issuer'ı olur, Secret Key (SK) imzalama anahtarıdır.
        """
        headers = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": self._settings.kling_access_key,
            "exp": now + self.JWT_TTL,
            "nbf": now - 5,
        }
        return jwt.encode(payload, self._settings.kling_secret_key, headers=headers)

    def _get_headers(self) -> dict[str, str]:
        """Authorization header'ları ile request headers."""
        return {
            "Authorization": f"Bearer {self._generate_jwt()}",
            "Content-Type": "application/json",
        }

    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        duration: int = 5,
        mode: str = "std",
        negative_prompt: str = "",
    ) -> bytes:
        """Text'ten video uretir (text-to-video).

        Args:
            prompt: Video aciklamasi (max 2500 karakter).
            aspect_ratio: En-boy orani ("16:9", "9:16", "1:1").
            duration: Video suresi — 5 veya 10 saniye.
            mode: Uretim kalitesi — "std" (~30sn) veya "pro" (~60sn).
            negative_prompt: Videonun icermemesi gerekenler.

        Returns:
            bytes: Uretilen videonun binary datasi (MP4).
        """
        endpoint = f"{self.BASE_URL}/v1/videos/text2video"

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
            "mode": mode,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )
            self._check_response(response)

            data = response.json()
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"task_id bulunamadi: {data}")

        print(f"[kling] Text-to-video task olusturuldu: {task_id}")

        video_url = await self._poll_task(task_id)
        return await self._download_video(video_url)

    async def generate_video_from_image(
        self,
        prompt: str,
        image_url: str,
        aspect_ratio: str = "9:16",
        duration: int = 5,
        mode: str = "std",
        negative_prompt: str = "",
    ) -> bytes:
        """Image'dan video uretir (image-to-video).

        Args:
            prompt: Hareket/sahne aciklamasi (max 2500 karakter).
            image_url: Kaynak gorsel URL'i (JPEG, PNG, WEBP — max 10MB).
            aspect_ratio: En-boy orani ("16:9", "9:16", "1:1").
            duration: Video suresi — 5 veya 10 saniye.
            mode: Uretim kalitesi — "std" veya "pro".
            negative_prompt: Videonun icermemesi gerekenler.

        Returns:
            bytes: Uretilen videonun binary datasi (MP4).
        """
        endpoint = f"{self.BASE_URL}/v1/videos/image2video"

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "image": image_url,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
            "mode": mode,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )
            self._check_response(response)

            data = response.json()
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"task_id bulunamadi: {data}")

        print(f"[kling] Image-to-video task olusturuldu: {task_id}")

        video_url = await self._poll_task(task_id)
        return await self._download_video(video_url)

    async def _poll_task(self, task_id: str) -> str:
        """Task durumunu poll eder, tamamlaninca video URL dondurur.

        Args:
            task_id: Kling task ID.

        Returns:
            str: Uretilen videonun CDN URL'i.

        Raises:
            RuntimeError: Task basarisiz olursa.
            TimeoutError: Max bekleme suresi asildiysa.
        """
        poll_url = f"{self.BASE_URL}/v1/videos/{task_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = await client.get(
                    poll_url,
                    headers=self._get_headers(),
                )
                self._check_response(response)

                data = response.json().get("data", {})
                status = data.get("task_status")

                if status == "succeed":
                    works = data.get("output", {}).get("works", [])
                    if works and works[0].get("url"):
                        return works[0]["url"]
                    raise RuntimeError(f"Video URL bulunamadi: {data}")

                if status == "failed":
                    raise RuntimeError(
                        f"Kling video uretimi basarisiz: {data.get('task_status_msg', 'bilinmeyen hata')}"
                    )

                # submitted veya processing — beklemeye devam
                print(
                    f"[kling] Poll {attempt + 1}/{self.MAX_POLL_ATTEMPTS} — "
                    f"status: {status}"
                )
                await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(
            f"Kling video uretimi zaman asimina ugradi "
            f"({self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} saniye)"
        )

    async def _download_video(self, video_url: str) -> bytes:
        """CDN URL'den video indirir.

        Args:
            video_url: Kling CDN video URL.

        Returns:
            bytes: Video binary data (MP4).
        """
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            response = await client.get(video_url)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Video indirme hatasi {response.status_code}: {response.text[:200]}"
                )
            return response.content

    @staticmethod
    def _check_response(response: httpx.Response) -> None:
        """HTTP response'u kontrol eder, hata varsa RuntimeError firlatir."""
        if response.status_code != 200:
            raise RuntimeError(
                f"Kling API Error {response.status_code}: {response.text[:500]}"
            )
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(
                f"Kling API Error code={body.get('code')}: {body.get('message', 'bilinmeyen hata')}"
            )


@lru_cache(maxsize=1)
def get_kling_client() -> KlingVideoClient:
    """KlingVideoClient instance dondurur (cached)."""
    return KlingVideoClient()


__all__ = ["KlingVideoClient", "get_kling_client"]
