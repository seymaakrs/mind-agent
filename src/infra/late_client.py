"""Late API client for Instagram/YouTube posting and analytics."""

from __future__ import annotations

from typing import Any, Literal

import httpx


class LateClient:
    """Client for Late API (Instagram posting service)."""

    BASE_URL = "https://getlate.dev/api/v1"
    TIMEOUT = 120  # seconds

    def __init__(self, api_key: str, account_id: str) -> None:
        """
        Initialize Late API client.

        Args:
            api_key: Late API key (sk_live_xxxxx or sk_test_xxxxx)
            account_id: Late account ID (acc_xxxxx)
        """
        self.api_key = api_key
        self.account_id = account_id

    def _get_headers(self) -> dict[str, str]:
        """Return authorization headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
        # Both stories and feed posts need type
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

        # Build platformSpecificData
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
            # Late API requires content field - stories need placeholder (won't be displayed)
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

        # Build tiktokSettings - required fields
        tiktok_settings: dict[str, Any] = {
            "privacy_level": privacy_level,
            "allow_comment": allow_comment,
            "media_type": "photo",
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }

        # Optional fields
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

    def _build_linkedin_platform_data(
        self,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
    ) -> dict[str, Any]:
        """Build LinkedIn platform entry with optional platformSpecificData."""
        platform_data: dict[str, Any] = {
            "platform": "linkedin",
            "accountId": self.account_id,
        }

        psd: dict[str, Any] = {}
        if first_comment is not None:
            psd["firstComment"] = first_comment
        if disable_link_preview is not None:
            psd["disableLinkPreview"] = disable_link_preview
        if organization_urn is not None:
            psd["organizationUrn"] = organization_urn

        if psd:
            platform_data["platformSpecificData"] = psd

        return platform_data

    async def post_linkedin(
        self,
        content: str | None = None,
        media_url: str | None = None,
        media_type: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> dict[str, Any]:
        """
        Post to LinkedIn (text-only, single image, or video).

        Args:
            content: Post text (max 3000 chars). Optional if media attached.
            media_url: Public URL of image or video (optional).
            media_type: "image" or "video" (required if media_url provided).
            first_comment: Auto-posted first comment (good for links).
            disable_link_preview: Suppress URL preview card.
            organization_urn: Post as company page (urn:li:organization:XXXXX).
            scheduled_for: ISO datetime for scheduled post.

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status.
        """
        payload: dict[str, Any] = {
            "platforms": [self._build_linkedin_platform_data(
                first_comment=first_comment,
                disable_link_preview=disable_link_preview,
                organization_urn=organization_urn,
            )],
            "publishNow": scheduled_for is None,
        }

        if content:
            payload["content"] = content
        if media_url and media_type:
            payload["mediaItems"] = [{"type": media_type, "url": media_url}]
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
            li_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": li_platform.get("platformPostId"),
                "platform_post_url": li_platform.get("platformPostUrl"),
                "status": li_platform.get("status"),
            }

    async def post_linkedin_carousel(
        self,
        media_items: list[dict[str, str]],
        content: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> dict[str, Any]:
        """
        Post multi-image carousel to LinkedIn (2-20 images).

        Args:
            media_items: List of image items [{"type": "image", "url": "..."}, ...].
            content: Post text (max 3000 chars, optional).
            first_comment: Auto-posted first comment.
            disable_link_preview: Suppress URL preview card.
            organization_urn: Post as company page.
            scheduled_for: ISO datetime for scheduled post.

        Returns:
            dict with post_id, platform_post_id, platform_post_url, status, item_count.
        """
        formatted_items = [
            {"type": item.get("type", "image"), "url": item["url"]}
            for item in media_items
        ]

        payload: dict[str, Any] = {
            "mediaItems": formatted_items,
            "platforms": [self._build_linkedin_platform_data(
                first_comment=first_comment,
                disable_link_preview=disable_link_preview,
                organization_urn=organization_urn,
            )],
            "publishNow": scheduled_for is None,
        }

        if content:
            payload["content"] = content
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
            li_platform = platforms[0] if platforms else {}

            return {
                "success": True,
                "post_id": post.get("_id"),
                "platform_post_id": li_platform.get("platformPostId"),
                "platform_post_url": li_platform.get("platformPostUrl"),
                "status": li_platform.get("status"),
                "item_count": len(media_items),
            }

    async def get_analytics(
        self,
        post_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        page: int = 1,
        sort_by: Literal["date", "engagement"] = "date",
        order: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """
        Get analytics for Instagram account or a specific post.

        Args:
            post_id: Specific post ID (Late ID or External ID). If provided, returns single post.
            date_from: Start date filter (YYYY-MM-DD format).
            date_to: End date filter (YYYY-MM-DD format).
            limit: Posts per page (default 50, range 1-100).
            page: Page number (default 1).
            sort_by: Sort field - "date" or "engagement" (default: "date").
            order: Sort direction - "asc" or "desc" (default: "desc").

        Returns:
            List mode: {success, posts[], pagination{}}
            Single mode: {success, post{}}
        """
        params: dict[str, Any] = {
            "platform": "instagram",
        }

        if post_id:
            # Tekil post modu - postId parametresi ile cagir
            params["postId"] = post_id
        else:
            # Liste modu - Late API profileId + fromDate/toDate kullanıyor
            params["profileId"] = self.account_id
            params["limit"] = max(1, min(limit, 100))  # Clamp 1-100
            params["page"] = max(1, page)
            params["sortBy"] = sort_by
            params["order"] = order
            if date_from:
                params["fromDate"] = date_from
            if date_to:
                params["toDate"] = date_to

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(
                f"{self.BASE_URL}/analytics",
                headers=self._get_headers(),
                params=params,
            )

            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

            data = response.json()

            # Tekil post response
            if post_id:
                return {
                    "success": True,
                    "post": data,
                }

            # Liste response - pagination bilgisi ekle
            pagination = data.get("pagination", {})
            return {
                "success": True,
                "posts": data.get("posts", []),
                "pagination": {
                    "total": pagination.get("total", 0),
                    "page": pagination.get("page", 1),
                    "limit": pagination.get("limit", limit),
                    "total_pages": pagination.get("totalPages", 1),
                },
            }

    async def get_post_analytics(self, post_id: str) -> dict[str, Any]:
        """
        DEPRECATED: Use get_analytics(post_id=...) instead.

        Get analytics for a specific post.

        Args:
            post_id: Late post ID or External Post ID.

        Returns:
            dict with post analytics.
        """
        # Delegate to unified get_analytics method
        return await self.get_analytics(post_id=post_id)

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
        # Build media item - type is required for Late API to recognize as video
        media_item: dict[str, Any] = {
            "type": "video",
            "url": video_url,
        }

        # Add thumbnail if provided (only works for videos >3min)
        if thumbnail_url:
            media_item["thumbnail"] = {"url": thumbnail_url}

        # Build platform specific data (all optional)
        platform_specific: dict[str, Any] = {}
        if title:
            platform_specific["title"] = title
        if visibility:
            platform_specific["visibility"] = visibility
        if made_for_kids:
            platform_specific["madeForKids"] = made_for_kids
        if first_comment:
            platform_specific["firstComment"] = first_comment

        # Build platform data
        platform_data: dict[str, Any] = {
            "platform": "youtube",
            "accountId": self.account_id,
        }

        if platform_specific:
            platform_data["platformSpecificData"] = platform_specific

        # Build payload - only required fields + optionals
        payload: dict[str, Any] = {
            "mediaItems": [media_item],
            "platforms": [platform_data],
            "publishNow": scheduled_for is None,
        }

        # Add optional fields
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

    async def get_accounts(self, platform: str | None = "instagram") -> dict[str, Any]:
        """
        Get connected accounts list.

        Args:
            platform: Filter by platform (optional, default "instagram").

        Returns:
            dict with accounts list.
        """
        params: dict[str, str] = {}
        if platform:
            params["platform"] = platform

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(
                f"{self.BASE_URL}/accounts",
                headers=self._get_headers(),
                params=params,
            )

            if response.status_code >= 400:
                return {
                    "success": False,
                    "error": response.text,
                    "status_code": response.status_code,
                }

            data = response.json()
            return {
                "success": True,
                "accounts": data.get("accounts", []),
            }


def get_late_client(account_id: str, strip_prefix: bool = True) -> LateClient:
    """
    Create LateClient instance with API key from config.

    Args:
        account_id: Late account ID (acc_xxxxx for posting, raw ObjectId for analytics).
        strip_prefix: If True, strips "acc_" prefix (for posting).
                      If False, uses ID as-is (for analytics with late_profile_id).

    Returns:
        LateClient instance.

    Raises:
        ValueError: If LATE_API_KEY is not configured.
    """
    from src.app.config import get_settings

    settings = get_settings()
    if not settings.late_api_key:
        raise ValueError("LATE_API_KEY is not configured")

    # Strip "acc_" prefix only for posting operations (instagram_id)
    # Analytics uses late_profile_id which is already raw ObjectId
    if strip_prefix and account_id.startswith("acc_"):
        account_id = account_id[4:]

    return LateClient(settings.late_api_key, account_id)
