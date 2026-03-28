"""LinkedIn posting methods for Late API client."""

from __future__ import annotations

from typing import Any

import httpx


class _LinkedInMixin:
    """LinkedIn-specific Late API methods (single post, carousel)."""

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
