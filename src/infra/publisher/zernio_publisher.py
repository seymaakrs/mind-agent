"""``PublisherClient`` adapter backed by ``ZernioClient.create_post``.

Each method builds the canonical ``POST /v1/posts`` payload for one
platform and dispatches through the Zernio Posts mixin. The Late
adapter's signatures are mirrored exactly so the tool layer can swap
backends with no call-site changes.
"""
from __future__ import annotations

from typing import Any, Literal

from src.infra.errors import ServiceError, classify_error

from .base import PublishResult


# Common payload-builder helpers --------------------------------------------


def _ig_platform_specific(
    *,
    is_story: bool,
    first_comment: str | None,
    thumbnail_url: str | None,
    media_type: str | None,
) -> dict[str, Any]:
    psd: dict[str, Any] = {}
    if is_story:
        psd["contentType"] = "story"
    if first_comment and not is_story:
        psd["firstComment"] = first_comment
    if thumbnail_url and media_type == "video" and not is_story:
        psd["instagramThumbnail"] = thumbnail_url
    return psd


def _linkedin_platform_specific(
    *,
    first_comment: str | None,
    disable_link_preview: bool | None,
    organization_urn: str | None,
) -> dict[str, Any]:
    psd: dict[str, Any] = {}
    if first_comment is not None:
        psd["firstComment"] = first_comment
    if disable_link_preview is not None:
        psd["disableLinkPreview"] = disable_link_preview
    if organization_urn is not None:
        psd["organizationUrn"] = organization_urn
    return psd


def _youtube_platform_specific(
    *,
    title: str | None,
    visibility: str,
    made_for_kids: bool,
    first_comment: str | None,
) -> dict[str, Any]:
    psd: dict[str, Any] = {
        "visibility": visibility,
        "madeForKids": made_for_kids,
    }
    if title is not None:
        psd["title"] = title
    if first_comment is not None:
        psd["firstComment"] = first_comment
    return psd


def _build_tiktok_settings_video(
    *,
    privacy_level: str,
    allow_comment: bool,
    allow_duet: bool,
    allow_stitch: bool,
    video_cover_timestamp_ms: int | None,
    video_made_with_ai: bool | None,
    draft: bool | None,
    commercial_content_type: str | None,
) -> dict[str, Any]:
    s: dict[str, Any] = {
        "privacyLevel": privacy_level,
        "allowComment": allow_comment,
        "allowDuet": allow_duet,
        "allowStitch": allow_stitch,
        "mediaType": "video",
        "contentPreviewConfirmed": True,
        "expressConsentGiven": True,
    }
    if video_cover_timestamp_ms is not None:
        s["videoCoverTimestampMs"] = video_cover_timestamp_ms
    if video_made_with_ai is not None:
        s["videoMadeWithAi"] = video_made_with_ai
    if draft is not None:
        s["draft"] = draft
    if commercial_content_type is not None:
        s["commercialContentType"] = commercial_content_type
    return s


def _build_tiktok_settings_carousel(
    *,
    privacy_level: str,
    allow_comment: bool,
    description: str | None,
    photo_cover_index: int | None,
    auto_add_music: bool | None,
    video_made_with_ai: bool | None,
    draft: bool | None,
    commercial_content_type: str | None,
) -> dict[str, Any]:
    s: dict[str, Any] = {
        "privacyLevel": privacy_level,
        "allowComment": allow_comment,
        "mediaType": "photo",
        "contentPreviewConfirmed": True,
        "expressConsentGiven": True,
    }
    if description is not None:
        s["description"] = description
    if photo_cover_index is not None:
        s["photoCoverIndex"] = photo_cover_index
    if auto_add_music is not None:
        s["autoAddMusic"] = auto_add_music
    if video_made_with_ai is not None:
        s["videoMadeWithAi"] = video_made_with_ai
    if draft is not None:
        s["draft"] = draft
    if commercial_content_type is not None:
        s["commercialContentType"] = commercial_content_type
    return s


# Response normalizer -------------------------------------------------------


def _from_zernio_response(
    raw: dict[str, Any],
    *,
    type_label: str | None = None,
    item_count: int | None = None,
) -> PublishResult:
    post = raw.get("post", {}) if isinstance(raw, dict) else {}
    platforms = post.get("platforms", []) if isinstance(post, dict) else []
    first = platforms[0] if platforms else {}
    return PublishResult(
        success=True,
        post_id=post.get("_id"),
        platform_post_id=first.get("platformPostId"),
        platform_post_url=first.get("platformPostUrl"),
        status=first.get("status") or post.get("status"),
        published_at=first.get("publishedAt") or post.get("publishedAt"),
        type=type_label,
        item_count=item_count,
        raw=raw,
    )


def _exception_to_result(exc: Exception) -> PublishResult:
    classified = classify_error(exc, "zernio")
    status_code = (
        exc.status_code if isinstance(exc, ServiceError) else classified.get("status_code")
    )
    return PublishResult(
        success=False,
        error=classified.get("error") or str(exc),
        status_code=status_code,
        raw=classified,
    )


# Adapter -------------------------------------------------------------------


class ZernioPublisher:
    """``PublisherClient`` over ``ZernioClient.create_post``."""

    backend = "zernio"

    def __init__(self, account_id: str) -> None:
        # Lazy import so this module is import-safe even when ZERNIO_API_KEY
        # is unset.
        from src.infra.zernio import get_zernio_client

        self.account_id = account_id
        self._client = get_zernio_client()

    async def _create_post(
        self,
        *,
        content: str | None,
        media_items: list[dict[str, str]] | None,
        platform: str,
        platform_specific_data: dict[str, Any] | None = None,
        tiktok_settings: dict[str, Any] | None = None,
        scheduled_for: str | None = None,
        publish_now: bool = True,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        platform_entry: dict[str, Any] = {
            "platform": platform,
            "accountId": self.account_id,
        }
        if platform_specific_data:
            platform_entry["platformSpecificData"] = platform_specific_data

        return await self._client.create_post(
            content=content,
            platforms=[platform_entry],
            media_items=media_items,
            scheduled_for=scheduled_for,
            publish_now=publish_now and scheduled_for is None,
            tiktok_settings=tiktok_settings,
            tags=tags,
        )

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
            raw = await self._create_post(
                content="." if is_story else caption,
                media_items=[{"type": media_type, "url": media_url}],
                platform="instagram",
                platform_specific_data=_ig_platform_specific(
                    is_story=is_story,
                    first_comment=first_comment,
                    thumbnail_url=thumbnail_url,
                    media_type=media_type,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(
            raw, type_label="story" if is_story else media_type
        )

    async def instagram_carousel(
        self,
        media_items: list[dict[str, str]],
        caption: str,
        first_comment: str | None = None,
    ) -> PublishResult:
        if not 2 <= len(media_items) <= 10:
            return PublishResult(
                success=False,
                error=f"Carousel must have 2-10 items, got {len(media_items)}",
            )
        formatted = [{"type": i.get("type", "image"), "url": i["url"]} for i in media_items]
        try:
            raw = await self._create_post(
                content=caption,
                media_items=formatted,
                platform="instagram",
                platform_specific_data=(
                    {"firstComment": first_comment} if first_comment else None
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(raw, type_label="carousel", item_count=len(media_items))

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
        media_items = (
            [{"type": media_type or "image", "url": media_url}] if media_url else None
        )
        try:
            raw = await self._create_post(
                content=content,
                media_items=media_items,
                platform="linkedin",
                platform_specific_data=_linkedin_platform_specific(
                    first_comment=first_comment,
                    disable_link_preview=disable_link_preview,
                    organization_urn=organization_urn,
                ),
                scheduled_for=scheduled_for,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(
            raw, type_label=media_type if media_url else "text"
        )

    async def linkedin_carousel(
        self,
        media_items: list[dict[str, str]],
        content: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> PublishResult:
        if not 2 <= len(media_items) <= 20:
            return PublishResult(
                success=False,
                error=f"LinkedIn carousel must have 2-20 items, got {len(media_items)}",
            )
        formatted = [{"type": i.get("type", "image"), "url": i["url"]} for i in media_items]
        try:
            raw = await self._create_post(
                content=content,
                media_items=formatted,
                platform="linkedin",
                platform_specific_data=_linkedin_platform_specific(
                    first_comment=first_comment,
                    disable_link_preview=disable_link_preview,
                    organization_urn=organization_urn,
                ),
                scheduled_for=scheduled_for,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(
            raw, type_label="carousel", item_count=len(media_items)
        )

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
        settings = _build_tiktok_settings_video(
            privacy_level=privacy_level,
            allow_comment=allow_comment,
            allow_duet=allow_duet,
            allow_stitch=allow_stitch,
            video_cover_timestamp_ms=video_cover_timestamp_ms,
            video_made_with_ai=video_made_with_ai,
            draft=draft,
            commercial_content_type=commercial_content_type,
        )
        try:
            raw = await self._create_post(
                content=content,
                media_items=[{"type": "video", "url": video_url}],
                platform="tiktok",
                tiktok_settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(raw, type_label="video")

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
        if not 1 <= len(media_items) <= 35:
            return PublishResult(
                success=False,
                error=f"TikTok carousel must have 1-35 items, got {len(media_items)}",
            )
        formatted = [{"type": i.get("type", "image"), "url": i["url"]} for i in media_items]
        settings = _build_tiktok_settings_carousel(
            privacy_level=privacy_level,
            allow_comment=allow_comment,
            description=description,
            photo_cover_index=photo_cover_index,
            auto_add_music=auto_add_music,
            video_made_with_ai=video_made_with_ai,
            draft=draft,
            commercial_content_type=commercial_content_type,
        )
        try:
            raw = await self._create_post(
                content=content,
                media_items=formatted,
                platform="tiktok",
                tiktok_settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(
            raw, type_label="carousel", item_count=len(media_items)
        )

    # ----- YouTube -------------------------------------------------------

    # ----- Analytics ----------------------------------------------------

    async def get_analytics(
        self,
        *,
        post_id: str | None = None,
        profile_id: str | None = None,
        platform: str = "instagram",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        page: int = 1,
        sort_by: str = "date",
        order: str = "desc",
    ) -> dict[str, Any]:
        """Delegate to ZernioClient.get_analytics and normalize the shape.

        Zernio's response carries the post fields at the top level for
        single-post mode (``{postId, latePostId, analytics, ...}``) and
        under ``posts`` for list mode, with list items keyed by ``_id``
        instead of ``postId``. We rewrap them into Late's historical
        ``{success, post, ...}`` / ``{success, posts, pagination, ...}``
        envelope so the tool layer can consume both backends with one
        code path.
        """
        try:
            raw = await self._client.get_analytics(
                post_id=post_id,
                profile_id=profile_id or self.account_id,
                platform=platform,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                page=page,
                sort_by=sort_by,
                order=order,
            )
        except Exception as exc:  # noqa: BLE001
            classified = classify_error(exc, "zernio")
            return {
                "success": False,
                "error": classified.get("error") or str(exc),
                "status_code": (
                    exc.status_code if isinstance(exc, ServiceError)
                    else classified.get("status_code")
                ),
            }

        if post_id:
            return {"success": True, "post": raw}

        posts = list(raw.get("posts", []) or [])
        for p in posts:
            # Zernio list items expose `_id`; tool code reads `postId`.
            if isinstance(p, dict) and "postId" not in p and "_id" in p:
                p["postId"] = p["_id"]

        out: dict[str, Any] = {
            "success": True,
            "posts": posts,
            "pagination": raw.get("pagination", {}),
        }
        if "overview" in raw:
            out["overview"] = raw["overview"]
        if "accounts" in raw:
            out["accounts"] = raw["accounts"]
        return out

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
        media_item: dict[str, Any] = {"type": "video", "url": video_url}
        if thumbnail_url:
            media_item["thumbnail"] = {"url": thumbnail_url}
        try:
            raw = await self._create_post(
                content=description,
                media_items=[media_item],
                platform="youtube",
                platform_specific_data=_youtube_platform_specific(
                    title=title,
                    visibility=visibility,
                    made_for_kids=made_for_kids,
                    first_comment=first_comment,
                ),
                scheduled_for=scheduled_for,
                tags=tags,
            )
        except Exception as exc:  # noqa: BLE001
            return _exception_to_result(exc)
        return _from_zernio_response(raw, type_label="video")
