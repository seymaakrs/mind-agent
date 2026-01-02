from __future__ import annotations

import asyncio

import httpx


class InstagramClient:
    """Instagram Graph API client for posting media."""

    BASE_URL = "https://graph.facebook.com/v23.0"
    POLL_INTERVAL = 10  # seconds
    MAX_POLL_ATTEMPTS = 30  # 5 minutes max wait for video processing

    def __init__(self, account_id: str, access_token: str) -> None:
        """
        Initialize Instagram client.

        Args:
            account_id: Instagram Business Account ID.
            access_token: Facebook/Instagram Graph API access token.
        """
        self.account_id = account_id
        self.access_token = access_token

    def _get_headers(self) -> dict[str, str]:
        """Request headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def post_image(self, image_url: str, caption: str) -> dict:
        """
        Instagram'a gorsel paylas.

        Args:
            image_url: Gorsel URL'i (JPG formati, public erisilebilir).
            caption: Post aciklamasi.

        Returns:
            dict: {success, post_id, creation_id}
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Create media container
            create_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media",
                headers=self._get_headers(),
                data={
                    "image_url": image_url,
                    "caption": caption,
                },
            )

            if create_response.status_code != 200:
                error_detail = create_response.text
                raise RuntimeError(f"Instagram media creation failed {create_response.status_code}: {error_detail}")

            create_data = create_response.json()
            creation_id = create_data.get("id")

            if not creation_id:
                raise RuntimeError(f"Creation ID not found in response: {create_data}")

            # Step 2: Wait a bit for processing
            await asyncio.sleep(5)

            # Step 3: Publish the media
            publish_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media_publish",
                headers=self._get_headers(),
                data={
                    "creation_id": creation_id,
                },
            )

            if publish_response.status_code != 200:
                error_detail = publish_response.text
                raise RuntimeError(f"Instagram media publish failed {publish_response.status_code}: {error_detail}")

            publish_data = publish_response.json()
            post_id = publish_data.get("id")

            return {
                "success": True,
                "post_id": post_id,
                "creation_id": creation_id,
                "type": "image",
            }

    async def post_video_reel(self, video_url: str, caption: str) -> dict:
        """
        Instagram'a video/Reel paylas.

        Args:
            video_url: Video URL'i (MP4 formati, public erisilebilir).
            caption: Post aciklamasi.

        Returns:
            dict: {success, post_id, creation_id}
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Create media container for REELS
            create_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media",
                headers=self._get_headers(),
                data={
                    "video_url": video_url,
                    "caption": caption,
                    "media_type": "REELS",
                    "access_token": self.access_token,
                },
            )

            if create_response.status_code != 200:
                error_detail = create_response.text
                raise RuntimeError(f"Instagram video creation failed {create_response.status_code}: {error_detail}")

            create_data = create_response.json()
            creation_id = create_data.get("id")

            if not creation_id:
                raise RuntimeError(f"Creation ID not found in response: {create_data}")

            # Step 2: Poll until video processing is complete
            await self._poll_video_status(client, creation_id)

            # Step 3: Publish the video
            publish_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media_publish",
                headers=self._get_headers(),
                data={
                    "creation_id": creation_id,
                    "access_token": self.access_token,
                },
            )

            if publish_response.status_code != 200:
                error_detail = publish_response.text
                raise RuntimeError(f"Instagram video publish failed {publish_response.status_code}: {error_detail}")

            publish_data = publish_response.json()
            post_id = publish_data.get("id")

            return {
                "success": True,
                "post_id": post_id,
                "creation_id": creation_id,
                "type": "reel",
            }

    async def _poll_video_status(self, client: httpx.AsyncClient, creation_id: str) -> None:
        """
        Video islemesinin tamamlanmasini bekler.

        Args:
            client: HTTP client instance.
            creation_id: Media container ID.
        """
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            status_response = await client.get(
                f"{self.BASE_URL}/{creation_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
            )

            if status_response.status_code != 200:
                error_detail = status_response.text
                raise RuntimeError(f"Instagram status check failed {status_response.status_code}: {error_detail}")

            status_data = status_response.json()
            status_code = status_data.get("status_code")

            if status_code == "FINISHED":
                return

            if status_code == "ERROR":
                error_msg = status_data.get("status", "Unknown error")
                raise RuntimeError(f"Instagram video processing failed: {error_msg}")

            # Still processing (IN_PROGRESS), wait and retry
            await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"Instagram video processing timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds")


__all__ = ["InstagramClient"]
