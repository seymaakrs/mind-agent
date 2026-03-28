"""YouTube posting methods for Late API client."""

from __future__ import annotations

from typing import Any, Literal

import httpx


class _YouTubeMixin:
    """YouTube-specific Late API methods (video posting)."""

    async def post_youtube_video(
        self,
        video_url: str,
        title: str | None = None,
        description: str | None = None,
        visibility: Literal["public", "unlisted", "private"] = "public",
        made_for_kids: bool = False,
        tags: list[str] | None = None,
        thumbnail_url: str | None = None,
        first_comment: str | None = None,
        scheduled_for: str | None = None,
    ) -> dict[str, Any]:
        """
        Post a video to YouTube via Late API.

        Args:
            video_url: Public URL of the video file (required).
            title: Video title (max 100 chars, optional).
            description: Video description (max 5000 chars, optional).
            visibility: "public", "unlisted", or "private" (default: public).
            made_for_kids: COPPA compliance flag (default: False).
            tags: List of tags (total 500 char limit, optional).
            thumbnail_url: Custom thumbnail URL (only for videos >3min, optional).
            first_comment: Pinned first comment (max 10000 chars, optional).
            scheduled_for: ISO datetime for scheduled upload (optional).

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status.
        """
        media_item: dict[str, Any] = {
            "type": "video",
            "url": video_url,
        }

        if thumbnail_url:
            media_item["thumbnail"] = {"url": thumbnail_url}

        platform_specific: dict[str, Any] = {}
        if title:
            platform_specific["title"] = title
        if visibility:
            platform_specific["visibility"] = visibility
        if made_for_kids:
            platform_specific["madeForKids"] = made_for_kids
        if first_comment:
            platform_specific["firstComment"] = first_comment

        platform_data: dict[str, Any] = {
            "platform": "youtube",
            "accountId": self.account_id,
        }

        if platform_specific:
            platform_data["platformSpecificData"] = platform_specific

        payload: dict[str, Any] = {
            "mediaItems": [media_item],
            "platforms": [platform_data],
            "publishNow": scheduled_for is None,
        }

        if description:
            payload["content"] = description
        if tags:
            payload["tags"] = tags
        if scheduled_for:
            payload["scheduledFor"] = scheduled_for

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
            yt_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": yt_platform.get("platformPostId"),
                "platform_post_url": yt_platform.get("platformPostUrl"),
                "status": yt_platform.get("status"),
                "published_at": post.get("publishedAt"),
            }
