from __future__ import annotations

import asyncio
from functools import lru_cache

import httpx

from src.app.config import get_settings


class CloudConvertClient:
    """CloudConvert API client for media format conversion."""

    BASE_URL = "https://api.cloudconvert.com/v2"
    POLL_INTERVAL = 5  # seconds
    MAX_POLL_ATTEMPTS = 120  # 10 minutes max wait

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.cloudconvert_api_key:
            raise ValueError("CLOUDCONVERT_API_KEY env degiskeni ayarlanmamis")

    @property
    def _api_key(self) -> str:
        return self._settings.cloudconvert_api_key

    def _get_headers(self) -> dict[str, str]:
        """Request headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def convert_image_to_jpg(self, source_url: str) -> str:
        """
        PNG/WebP gorselini JPG'ye cevirir (Instagram icin).

        Args:
            source_url: Kaynak gorsel URL'i (Firebase Storage public URL).

        Returns:
            str: Donusturulmus JPG dosyasinin URL'i.
        """
        job_payload = {
            "tasks": {
                "import-file": {
                    "operation": "import/url",
                    "url": source_url,
                },
                "convert-to-jpg": {
                    "operation": "convert",
                    "input": ["import-file"],
                    "output_format": "jpg",
                    "quality": 90,
                },
                "export-file": {
                    "operation": "export/url",
                    "input": ["convert-to-jpg"],
                },
            }
        }

        return await self._run_job(job_payload)

    async def convert_video_for_instagram(self, source_url: str) -> str:
        """
        Videoyu Instagram Reels icin uygun formata cevirir (MP4, x264, AAC).

        Args:
            source_url: Kaynak video URL'i (Firebase Storage public URL).

        Returns:
            str: Donusturulmus video dosyasinin URL'i.
        """
        job_payload = {
            "tasks": {
                "import-file": {
                    "operation": "import/url",
                    "url": source_url,
                },
                "convert-for-instagram": {
                    "operation": "convert",
                    "input": "import-file",
                    "output_format": "mp4",
                    "video_codec": "x264",
                    "audio_codec": "aac",
                    "preset": "fast",
                    "faststart": True,
                    "engine": "ffmpeg",
                },
                "export-file": {
                    "operation": "export/url",
                    "input": "convert-for-instagram",
                },
            }
        }

        return await self._run_job(job_payload)

    async def _run_job(self, job_payload: dict) -> str:
        """
        CloudConvert job'i calistirir ve sonuc URL'ini dondurur.

        Args:
            job_payload: Job tanimlama payload'i.

        Returns:
            str: Export edilen dosyanin URL'i.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Create job
            response = await client.post(
                f"{self.BASE_URL}/jobs",
                headers=self._get_headers(),
                json=job_payload,
            )
            if response.status_code != 201:
                error_detail = response.text
                raise RuntimeError(f"CloudConvert job creation failed {response.status_code}: {error_detail}")

            job_data = response.json()
            job_id = job_data["data"]["id"]

        # 2. Poll until finished
        exported_url = await self._poll_job(job_id)
        return exported_url

    async def _poll_job(self, job_id: str) -> str:
        """
        Job'in tamamlanmasini bekler ve export URL'ini dondurur.

        Args:
            job_id: CloudConvert job ID'si.

        Returns:
            str: Export edilen dosyanin URL'i.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = await client.get(
                    f"{self.BASE_URL}/jobs/{job_id}",
                    headers=self._get_headers(),
                )
                if response.status_code != 200:
                    error_detail = response.text
                    raise RuntimeError(f"CloudConvert poll failed {response.status_code}: {error_detail}")

                job_data = response.json()
                status = job_data["data"]["status"]

                if status == "finished":
                    # Find export task and get URL
                    tasks = job_data["data"]["tasks"]
                    for task in tasks:
                        if task["operation"] == "export/url" and task.get("result"):
                            files = task["result"].get("files", [])
                            if files:
                                return files[0]["url"]
                    raise RuntimeError("Export URL not found in finished job")

                if status == "error":
                    error_tasks = [t for t in job_data["data"]["tasks"] if t.get("status") == "error"]
                    error_msg = error_tasks[0].get("message", "Unknown error") if error_tasks else "Unknown error"
                    raise RuntimeError(f"CloudConvert job failed: {error_msg}")

                # Still processing, wait and retry
                await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"CloudConvert job timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds")


@lru_cache(maxsize=1)
def get_cloudconvert_client() -> CloudConvertClient:
    """CloudConvertClient instance dondurur (cached)."""
    return CloudConvertClient()


__all__ = ["CloudConvertClient", "get_cloudconvert_client"]
