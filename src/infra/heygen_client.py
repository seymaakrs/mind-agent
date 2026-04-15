from __future__ import annotations

import asyncio

import httpx

from src.app.config import get_settings
from src.infra.errors import ServiceError


class HeyGenClient:
    """HeyGen Video Agent REST API client.

    Supports text-to-video via HeyGen Video Agent API.
    Uses simple X-Api-Key header authentication.

    API Docs: https://docs.heygen.com/reference/generate-video-agent
    """

    API_BASE_URL = "https://api.heygen.com"
    UPLOAD_BASE_URL = "https://upload.heygen.com"
    POLL_INTERVAL = 20  # seconds
    MAX_POLL_ATTEMPTS = 30  # 10 minutes max wait

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.heygen_api_key:
            raise ValueError(
                "HEYGEN_API_KEY env degiskeni ayarlanmamis. "
                "API key'i app.heygen.com/settings adresinden alinabilir."
            )

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._settings.heygen_api_key,
            "Content-Type": "application/json",
        }

    async def upload_asset(self, image_url: str) -> str:
        """Bir gorsel URL'ini HeyGen'e upload eder ve asset_id dondurur.

        Args:
            image_url: Gorsel URL'i (JPEG veya PNG).

        Returns:
            str: HeyGen asset ID.
        """
        # Gorseli indir
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            dl_response = await client.get(image_url)
            if dl_response.status_code != 200:
                raise ServiceError(
                    f"Gorsel indirme hatasi {dl_response.status_code}: {image_url}",
                    status_code=dl_response.status_code, service="heygen",
                )
            image_data = dl_response.content

            # Content-Type'i URL'den tahmin et
            content_type = "image/jpeg"
            lower_url = image_url.lower()
            if ".png" in lower_url:
                content_type = "image/png"
            elif ".webp" in lower_url:
                content_type = "image/webp"

            # HeyGen'e upload et
            upload_response = await client.post(
                f"{self.UPLOAD_BASE_URL}/v1/asset",
                headers={
                    "X-Api-Key": self._settings.heygen_api_key,
                    "Content-Type": content_type,
                },
                content=image_data,
            )
            if upload_response.status_code != 200:
                raise ServiceError(
                    f"HeyGen asset upload hatasi {upload_response.status_code}: {upload_response.text[:200]}",
                    status_code=upload_response.status_code, service="heygen",
                )

            body = upload_response.json()
            asset_id = body.get("data", {}).get("id")
            if not asset_id:
                raise ServiceError(
                    f"HeyGen asset_id bulunamadi: {body}",
                    status_code=500, service="heygen",
                )

        print(f"[heygen] Asset upload tamamlandi: {asset_id}")
        return asset_id

    async def generate_video(
        self,
        prompt: str,
        orientation: str = "landscape",
        duration_sec: int | None = None,
        image_url: str | None = None,
    ) -> bytes:
        """HeyGen Video Agent ile video uretir.

        Args:
            prompt: Video aciklamasi. HeyGen AI sahne ve stili otomatik secer.
            orientation: Video yonu — "landscape" veya "portrait".
            duration_sec: Yaklasik video suresi saniye cinsinden (minimum 5).
            image_url: Opsiyonel referans gorsel URL'i. Gorseli HeyGen'e upload eder
                       ve video uretiminde referans olarak kullanir.

        Returns:
            bytes: Uretilen videonun binary datasi (MP4).
        """
        # Opsiyonel: gorsel varsa once upload et
        files: list[dict] = []
        if image_url and image_url.strip():
            asset_id = await self.upload_asset(image_url.strip())
            files = [{"asset_id": asset_id}]

        # Request body olustur
        config: dict = {"orientation": orientation}
        if duration_sec is not None:
            config["duration_sec"] = max(5, duration_sec)

        payload: dict = {
            "prompt": prompt,
            "config": config,
        }
        if files:
            payload["files"] = files

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.API_BASE_URL}/v1/video_agent/generate",
                headers=self._get_headers(),
                json=payload,
            )
            self._check_response(response)

            data = response.json()
            video_id = data.get("data", {}).get("video_id")
            if not video_id:
                raise ServiceError(
                    f"video_id bulunamadi: {data}",
                    status_code=500, service="heygen",
                )

        print(f"[heygen] Video Agent task olusturuldu: {video_id}")

        video_url = await self._poll_video(video_id)
        return await self._download_video(video_url)

    async def _poll_video(self, video_id: str) -> str:
        """Video durumunu poll eder, tamamlaninca video URL dondurur.

        Args:
            video_id: HeyGen video ID.

        Returns:
            str: Tamamlanan videonun download URL'i (7 gun gecerli).

        Raises:
            ServiceError: Video uretimi basarisiz olursa.
            TimeoutError: Max bekleme suresi asildiysa.
        """
        poll_url = f"{self.API_BASE_URL}/v1/video_status.get"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = await client.get(
                    poll_url,
                    headers=self._get_headers(),
                    params={"video_id": video_id},
                )
                self._check_response(response)

                data = response.json().get("data", {})
                status = data.get("status")

                if status == "completed":
                    video_url = data.get("video_url")
                    if not video_url:
                        raise ServiceError(
                            f"Video tamamlandi ama video_url bulunamadi: {data}",
                            status_code=500, service="heygen",
                        )
                    return video_url

                if status == "failed":
                    error_detail = data.get("error") or "bilinmeyen hata"
                    raise ServiceError(
                        f"HeyGen video uretimi basarisiz: {error_detail}",
                        status_code=500, service="heygen",
                    )

                # pending veya processing — devam
                print(
                    f"[heygen] Poll {attempt + 1}/{self.MAX_POLL_ATTEMPTS} — "
                    f"status: {status}"
                )
                await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(
            f"HeyGen video uretimi zaman asimina ugradi "
            f"({self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} saniye)"
        )

    async def _download_video(self, video_url: str) -> bytes:
        """HeyGen video URL'inden video indirir.

        Args:
            video_url: HeyGen video download URL (7 gun gecerli).

        Returns:
            bytes: Video binary data (MP4).
        """
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            response = await client.get(video_url)
            if response.status_code != 200:
                raise ServiceError(
                    f"Video indirme hatasi {response.status_code}: {response.text[:200]}",
                    status_code=response.status_code, service="heygen",
                )
            return response.content

    @staticmethod
    def _check_response(response: httpx.Response) -> None:
        """HTTP response'u kontrol eder, hata varsa ServiceError firlatir."""
        if response.status_code not in (200, 201):
            raise ServiceError(
                f"HeyGen API Error {response.status_code}: {response.text[:500]}",
                status_code=response.status_code, service="heygen",
            )
        body = response.json()
        # HeyGen basarili response'larda error=null doner
        if body.get("error") is not None:
            raise ServiceError(
                f"HeyGen API Error: {body.get('error')}",
                status_code=400, service="heygen",
            )


_heygen_client: HeyGenClient | None = None


def get_heygen_client() -> HeyGenClient:
    """HeyGenClient instance dondurur (lazy singleton)."""
    global _heygen_client
    if _heygen_client is None:
        _heygen_client = HeyGenClient()
    return _heygen_client


__all__ = ["HeyGenClient", "get_heygen_client"]
