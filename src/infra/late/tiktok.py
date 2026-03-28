"""TikTok posting methods for Late API client."""

from __future__ import annotations

from typing import Any

import httpx


class _TikTokMixin:
    """TikTok-specific Late API methods (carousel and video posting)."""

    async def post_tiktok_carousel(
        self,
        media_items: list[dict[str, str]],
        content: str,
        privacy_level: str,
        allow_comment: bool = True,
        description: str | None = None,
        photo_cover_index: int | None = None,
        auto_add_music: bool | None = None,
        video_made_with_ai: bool | None = None,
        draft: bool | None = None,
        commercial_content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Post a carousel (photo slideshow) to TikTok via Late API.

        Args:
            media_items: List of image items [{"type": "image", "url": "..."}, ...] (max 35).
            content: Carousel title (max 90 chars, hashtags/URLs auto-cleaned by TikTok).
            privacy_level: Creator's allowed privacy value (e.g. "PUBLIC_TO_EVERYONE").
            allow_comment: Allow comments (default True).
            description: Long caption (max 4000 chars). content is title, this is the real caption.
            photo_cover_index: Which photo is cover (0-indexed).
            auto_add_music: Let TikTok auto-add music.
            video_made_with_ai: AI disclosure flag.
            draft: Send to Creator Inbox instead of publishing.
            commercial_content_type: Commercial content disclosure.

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status, item_count.
        """
        formatted_items = [
            {"type": item.get("type", "image"), "url": item["url"]}
            for item in media_items
        ]

        tiktok_settings: dict[str, Any] = {
            "privacy_level": privacy_level,
            "allow_comment": allow_comment,
            "media_type": "photo",
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }

        if description is not None:
            tiktok_settings["description"] = description
        if photo_cover_index is not None:
            tiktok_settings["photo_cover_index"] = photo_cover_index
        if auto_add_music is not None:
            tiktok_settings["auto_add_music"] = auto_add_music
        if video_made_with_ai is not None:
            tiktok_settings["video_made_with_ai"] = video_made_with_ai
        if draft is not None:
            tiktok_settings["draft"] = draft
        if commercial_content_type is not None:
            tiktok_settings["commercialContentType"] = commercial_content_type

        payload: dict[str, Any] = {
            "content": content,
            "mediaItems": formatted_items,
            "platforms": [
                {"platform": "tiktok", "accountId": self.account_id}
            ],
            "tiktokSettings": tiktok_settings,
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
            tt_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": tt_platform.get("platformPostId"),
                "platform_post_url": tt_platform.get("platformPostUrl"),
                "status": tt_platform.get("status"),
                "type": "carousel",
                "item_count": len(media_items),
            }

    async def post_tiktok_video(
        self,
        video_url: str,
        content: str,
        privacy_level: str,
        allow_comment: bool = True,
        allow_duet: bool = True,
        allow_stitch: bool = True,
        video_cover_timestamp_ms: int | None = None,
        video_made_with_ai: bool | None = None,
        draft: bool | None = None,
        commercial_content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Post a video to TikTok via Late API.

        Args:
            video_url: Public URL of the video file (MP4/MOV/WebM, max 4GB, 3s-10min).
            content: Video caption (max 2200 chars).
            privacy_level: Creator's allowed privacy value.
            allow_comment: Allow comments (default True).
            allow_duet: Allow duet (default True). Required for video.
            allow_stitch: Allow stitch (default True). Required for video.
            video_cover_timestamp_ms: Cover frame timestamp in ms (default: 1000).
            video_made_with_ai: AI disclosure flag.
            draft: Send to Creator Inbox instead of publishing.
            commercial_content_type: Commercial content disclosure.

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status.
        """
        tiktok_settings: dict[str, Any] = {
            "privacy_level": privacy_level,
            "allow_comment": allow_comment,
            "allow_duet": allow_duet,
            "allow_stitch": allow_stitch,
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }

        if video_cover_timestamp_ms is not None:
            tiktok_settings["video_cover_timestamp_ms"] = video_cover_timestamp_ms
        if video_made_with_ai is not None:
            tiktok_settings["video_made_with_ai"] = video_made_with_ai
        if draft is not None:
            tiktok_settings["draft"] = draft
        if commercial_content_type is not None:
            tiktok_settings["commercialContentType"] = commercial_content_type

        payload: dict[str, Any] = {
            "content": content,
            "mediaItems": [{"type": "video", "url": video_url}],
            "platforms": [
                {"platform": "tiktok", "accountId": self.account_id}
            ],
            "tiktokSettings": tiktok_settings,
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
            tt_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": tt_platform.get("platformPostId"),
                "platform_post_url": tt_platform.get("platformPostUrl"),
                "status": tt_platform.get("status"),
                "type": "video",
            }
