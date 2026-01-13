from __future__ import annotations

import asyncio

import httpx


class InstagramClient:
    """Instagram Graph API client for posting media."""

    BASE_URL = "https://graph.facebook.com/v24.0"
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

    async def _create_carousel_item(
        self,
        client: httpx.AsyncClient,
        media_url: str,
        media_type: str,
    ) -> str:
        """
        Carousel icin tek bir item container olusturur.

        Args:
            client: HTTP client instance.
            media_url: Medya URL'i (public erisilebilir).
            media_type: "image" veya "video".

        Returns:
            Container ID.
        """
        data = {
            "is_carousel_item": "true",
            "access_token": self.access_token,
        }

        if media_type == "video":
            data["media_type"] = "VIDEO"
            data["video_url"] = media_url
        else:
            data["image_url"] = media_url

        response = await client.post(
            f"{self.BASE_URL}/{self.account_id}/media",
            data=data,
        )

        if response.status_code != 200:
            error_detail = response.text
            raise RuntimeError(f"Carousel item creation failed {response.status_code}: {error_detail}")

        response_data = response.json()
        container_id = response_data.get("id")

        if not container_id:
            raise RuntimeError(f"Container ID not found in response: {response_data}")

        return container_id

    async def _poll_container_status(self, client: httpx.AsyncClient, container_id: str) -> None:
        """
        Container islemesinin tamamlanmasini bekler.

        Args:
            client: HTTP client instance.
            container_id: Media container ID.
        """
        for attempt in range(self.MAX_POLL_ATTEMPTS):
            status_response = await client.get(
                f"{self.BASE_URL}/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
            )

            if status_response.status_code != 200:
                error_detail = status_response.text
                raise RuntimeError(f"Container status check failed {status_response.status_code}: {error_detail}")

            status_data = status_response.json()
            status_code = status_data.get("status_code")

            if status_code == "FINISHED":
                return

            if status_code == "ERROR":
                error_msg = status_data.get("status", "Unknown error")
                raise RuntimeError(f"Container processing failed: {error_msg}")

            # Still processing (IN_PROGRESS), wait and retry
            await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"Container processing timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds")

    async def post_carousel(
        self,
        media_items: list[dict],
        caption: str,
    ) -> dict:
        """
        Instagram'a carousel (coklu medya) paylas.

        Args:
            media_items: Medya listesi. Her item: {"url": str, "type": "image" | "video"}
            caption: Post aciklamasi.

        Returns:
            dict: {success, post_id, creation_id, item_count}
        """
        if len(media_items) < 2:
            raise ValueError("Carousel en az 2 medya icermeli")

        if len(media_items) > 10:
            raise ValueError("Carousel en fazla 10 medya icerebilir")

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: Create item containers for each media
            container_ids = []
            video_container_ids = []

            for item in media_items:
                media_url = item.get("url")
                media_type = item.get("type", "image")

                container_id = await self._create_carousel_item(client, media_url, media_type)
                container_ids.append(container_id)

                if media_type == "video":
                    video_container_ids.append(container_id)

            # Step 2: Poll video containers until ready
            for video_id in video_container_ids:
                await self._poll_container_status(client, video_id)

            # Step 3: Create carousel container
            children_str = ",".join(container_ids)
            carousel_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": children_str,
                    "caption": caption,
                    "access_token": self.access_token,
                },
            )

            if carousel_response.status_code != 200:
                error_detail = carousel_response.text
                raise RuntimeError(f"Carousel container creation failed {carousel_response.status_code}: {error_detail}")

            carousel_data = carousel_response.json()
            creation_id = carousel_data.get("id")

            if not creation_id:
                raise RuntimeError(f"Carousel creation ID not found in response: {carousel_data}")

            # Step 4: Poll carousel container until ready
            await self._poll_container_status(client, creation_id)

            # Step 5: Publish the carousel
            publish_response = await client.post(
                f"{self.BASE_URL}/{self.account_id}/media_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": self.access_token,
                },
            )

            if publish_response.status_code != 200:
                error_detail = publish_response.text
                raise RuntimeError(f"Carousel publish failed {publish_response.status_code}: {error_detail}")

            publish_data = publish_response.json()
            post_id = publish_data.get("id")

            return {
                "success": True,
                "post_id": post_id,
                "creation_id": creation_id,
                "type": "carousel",
                "item_count": len(media_items),
            }


__all__ = ["InstagramClient"]
