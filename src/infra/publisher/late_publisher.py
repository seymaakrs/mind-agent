"""``PublisherClient`` adapter backed by the existing ``LateClient``.

Each method delegates to the corresponding ``LateClient`` method and wraps
the returned dict in a ``PublishResult``. No payload transformation —
Late already returns the canonical ``{success, post_id, platform_post_id,
platform_post_url, status, ...}`` shape that ``PublishResult`` mirrors.

This adapter exists so the tool layer can call ``publisher.instagram_post``
without caring whether the backend is Late or Zernio. The Faz 3 cutover
flips ``get_publisher`` to return ``ZernioPublisher`` and the call sites
do not change.
"""
from __future__ import annotations

from typing import Any, Literal

from src.infra.errors import ServiceError, classify_error

from .base import PublishResult


def _from_late_dict(raw: dict[str, Any]) -> PublishResult:
    """Translate a LateClient response dict into PublishResult."""
    if not raw.get("success", False):
        return PublishResult(
            success=False,
            error=raw.get("error"),
            status_code=raw.get("status_code"),
            raw=raw,
        )
    return PublishResult(
        success=True,
        post_id=raw.get("post_id"),
        platform_post_id=raw.get("platform_post_id"),
        platform_post_url=raw.get("platform_post_url"),
        status=raw.get("status"),
        type=raw.get("type"),
        item_count=raw.get("item_count"),
        raw=raw,
    )


class LatePublisher:
    """``PublisherClient`` over ``LateClient``."""

    backend = "late"

    def __init__(self, account_id: str) -> None:
        # Imported lazily so this module is safe to import even when
        # LATE_API_KEY is unset (e.g. in unit tests that only exercise
        # ZernioPublisher).
        from src.infra.late import get_late_client

        self.account_id = account_id
        self._client = get_late_client(account_id)

    # ----- Instagram -----------------------------------------------------

    async def instagram_post(
        self,
        media_url: str,
        caption: str,
        media_type: Literal["image", "video"],
        thumbnail_url: str | None = None,
        first_comment: str | None = None,
        is_story: bool = False,
    ) -> PublishResult:
        try:
            raw = await self._client.post_media(
                media_url=media_url,
                caption=caption,
                media_type=media_type,
                thumbnail_url=thumbnail_url,
                first_comment=first_comment,
                is_story=is_story,
            )
        except (ServiceError, Exception) as exc:  # noqa: BLE001 — uniform fallback
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    async def instagram_carousel(
        self,
        media_items: list[dict[str, str]],
        caption: str,
        first_comment: str | None = None,
    ) -> PublishResult:
        try:
            raw = await self._client.post_carousel(
                media_items=media_items,
                caption=caption,
                first_comment=first_comment,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    # ----- LinkedIn ------------------------------------------------------

    async def linkedin_post(
        self,
        content: str | None = None,
        media_url: str | None = None,
        media_type: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> PublishResult:
        try:
            raw = await self._client.post_linkedin(
                content=content,
                media_url=media_url,
                media_type=media_type,
                first_comment=first_comment,
                disable_link_preview=disable_link_preview,
                organization_urn=organization_urn,
                scheduled_for=scheduled_for,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    async def linkedin_carousel(
        self,
        media_items: list[dict[str, str]],
        content: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> PublishResult:
        try:
            raw = await self._client.post_linkedin_carousel(
                media_items=media_items,
                content=content,
                first_comment=first_comment,
                disable_link_preview=disable_link_preview,
                organization_urn=organization_urn,
                scheduled_for=scheduled_for,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    # ----- TikTok --------------------------------------------------------

    async def tiktok_video(
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
    ) -> PublishResult:
        try:
            raw = await self._client.post_tiktok_video(
                video_url=video_url,
                content=content,
                privacy_level=privacy_level,
                allow_comment=allow_comment,
                allow_duet=allow_duet,
                allow_stitch=allow_stitch,
                video_cover_timestamp_ms=video_cover_timestamp_ms,
                video_made_with_ai=video_made_with_ai,
                draft=draft,
                commercial_content_type=commercial_content_type,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    async def tiktok_carousel(
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
    ) -> PublishResult:
        try:
            raw = await self._client.post_tiktok_carousel(
                media_items=media_items,
                content=content,
                privacy_level=privacy_level,
                allow_comment=allow_comment,
                description=description,
                photo_cover_index=photo_cover_index,
                auto_add_music=auto_add_music,
                video_made_with_ai=video_made_with_ai,
                draft=draft,
                commercial_content_type=commercial_content_type,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)

    # ----- YouTube -------------------------------------------------------

    async def youtube_video(
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
    ) -> PublishResult:
        try:
            raw = await self._client.post_youtube_video(
                video_url=video_url,
                title=title,
                description=description,
                visibility=visibility,
                made_for_kids=made_for_kids,
                tags=tags,
                thumbnail_url=thumbnail_url,
                first_comment=first_comment,
                scheduled_for=scheduled_for,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc, "late")
        return _from_late_dict(raw)


def _exception_to_result(exc: Exception, service: str) -> PublishResult:
    """Translate a raised exception (HTTP error, network, etc.) into PublishResult.

    Late tools historically also accept ServiceError from the client side
    (the raw HTTPX exceptions never surface — Late client traps 4xx). We
    still wrap defensively so a programmer bug at the adapter boundary
    does not crash the caller.
    """
    classified = classify_error(exc, service)
    return PublishResult(
        success=False,
        error=classified.get("error") or str(exc),
        status_code=classified.get("status_code"),
        raw=classified,
    )
