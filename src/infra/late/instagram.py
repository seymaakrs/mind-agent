"""Instagram posting methods for Late API client."""

from __future__ import annotations

from typing import Any, Literal

import httpx


class _InstagramMixin:
    """Instagram-specific Late API methods (post_media, post_carousel)."""

    async def post_media(
        self,
        media_url: str,
        caption: str,
        media_type: Literal["image", "video"],
        thumbnail_url: str | None = None,
        first_comment: str | None = None,
        is_story: bool = False,
    ) -> dict[str, Any]:
        """
        Post image or video (reel) to Instagram, or post a story.

        Args:
            media_url: Public URL of the media file.
            caption: Post caption (ignored for stories).
            media_type: "image" or "video" (video = Reels for feed, video story for stories).
            thumbnail_url: Custom thumbnail URL for Reels (optional).
            first_comment: First comment to add after posting (optional, ignored for stories).
            is_story: If True, post as Instagram Story instead of feed post.

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status.
        """
        media_item: dict[str, Any] = {
            "type": media_type,
            "url": media_url,
        }

        if thumbnail_url and media_type == "video" and not is_story:
            media_item["instagramThumbnail"] = thumbnail_url

        platform_data: dict[str, Any] = {
            "platform": "instagram",
            "accountId": self.account_id,
        }

        platform_specific: dict[str, Any] = {}
        if is_story:
            platform_specific["contentType"] = "story"
        if first_comment and not is_story:
            platform_specific["firstComment"] = first_comment

        if platform_specific:
            platform_data["platformSpecificData"] = platform_specific

        payload: dict[str, Any] = {
            "mediaItems": [media_item],
            "platforms": [platform_data],
            "publishNow": True,
            "content": "." if is_story else caption,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                f"{self.BASE_URL}/posts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

            data = response.json()
            post = data.get("post", {})
            platforms = post.get("platforms", [])
            ig_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": ig_platform.get("platformPostId"),
                "platform_post_url": ig_platform.get("platformPostUrl"),
                "status": ig_platform.get("status"),
                "type": "story" if is_story else media_type,
            }

    async def post_carousel(
        self,
        media_items: list[dict[str, str]],
        caption: str,
        first_comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Post carousel (2-10 items) to Instagram.

        Args:
            media_items: List of media items [{"url": str, "type": "image"|"video"}, ...]
            caption: Post caption.
            first_comment: First comment to add after posting (optional).

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status, item_count.
        """
        if len(media_items) < 2 or len(media_items) > 10:
            return {
                "success": False,
                "error": f"Carousel must have 2-10 items, got {len(media_items)}",
            }

        formatted_items = [
            {"type": item.get("type", "image"), "url": item["url"]}
            for item in media_items
        ]

        platform_data: dict[str, Any] = {
            "platform": "instagram",
            "accountId": self.account_id,
        }

        if first_comment:
            platform_data["platformSpecificData"] = {"firstComment": first_comment}

        payload = {
            "content": caption,
            "mediaItems": formatted_items,
            "platforms": [platform_data],
            "publishNow": True,
        }

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                f"{self.BASE_URL}/posts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

            data = response.json()
            post = data.get("post", {})
            platforms = post.get("platforms", [])
            ig_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": ig_platform.get("platformPostId"),
                "platform_post_url": ig_platform.get("platformPostUrl"),
                "status": ig_platform.get("status"),
                "type": "carousel",
                "item_count": len(media_items),
            }
