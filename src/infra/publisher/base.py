"""Shared types for the Publisher adapter layer.

The Publisher layer wraps the Zernio backend behind a single
``PublisherClient`` Protocol. The adapter POSTs to the canonical
``/posts`` payload (``mediaItems`` + ``platforms``) and returns a
``PublishResult`` so callers get a stable, backend-agnostic shape.

This module ships only the types. The concrete adapter lives in
``zernio_publisher.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass
class PublishResult:
    """Normalized response from a publish call.

    Both Late and Zernio return ``{post: {_id, platforms: [{platformPostId,
    platformPostUrl, status}]}}`` (Late) or ``{post: {...}}`` (Zernio) on
    success. ``PublishResult`` flattens the first platform entry into the
    top level so tool code stays terse, while keeping ``raw`` for any
    field the adapter did not surface.
    """

    success: bool
    post_id: str | None = None              # backend (Late / Zernio) post _id
    platform_post_id: str | None = None     # IG / TT / LI / YT native post id
    platform_post_url: str | None = None    # public URL on the platform
    status: str | None = None               # "published" | "scheduled" | "failed" | ...
    type: str | None = None                 # "image" | "video" | "story" | "carousel"
    published_at: str | None = None         # ISO timestamp when the platform confirmed publish
    error: str | None = None
    status_code: int | None = None          # set when success=False
    item_count: int | None = None           # carousel size, when applicable
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Tool-layer friendly dict (matches today's Late return shape)."""
        out: dict[str, Any] = {
            "success": self.success,
            "post_id": self.post_id,
            "platform_post_id": self.platform_post_id,
            "platform_post_url": self.platform_post_url,
            "status": self.status,
        }
        if self.type is not None:
            out["type"] = self.type
        if self.item_count is not None:
            out["item_count"] = self.item_count
        if self.published_at is not None:
            out["published_at"] = self.published_at
        if not self.success:
            if self.error is not None:
                out["error"] = self.error
            if self.status_code is not None:
                out["status_code"] = self.status_code
        return out


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class PublisherClient(Protocol):
    """Backend-agnostic publish surface.

    Method names and parameter lists mirror today's ``LateClient`` so the
    Faz 3 cutover is a mechanical swap inside each tool — no spec
    refactor at the call site.
    """

    backend: str  # "late" | "zernio"
    account_id: str

    async def instagram_post(
        self,
        media_url: str,
        caption: str,
        media_type: Literal["image", "video"],
        thumbnail_url: str | None = None,
        first_comment: str | None = None,
        is_story: bool = False,
    ) -> PublishResult: ...

    async def instagram_carousel(
        self,
        media_items: list[dict[str, str]],
        caption: str,
        first_comment: str | None = None,
    ) -> PublishResult: ...

    async def linkedin_post(
        self,
        content: str | None = None,
        media_url: str | None = None,
        media_type: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> PublishResult: ...

    async def linkedin_carousel(
        self,
        media_items: list[dict[str, str]],
        content: str | None = None,
        first_comment: str | None = None,
        disable_link_preview: bool | None = None,
        organization_urn: str | None = None,
        scheduled_for: str | None = None,
    ) -> PublishResult: ...

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
    ) -> PublishResult: ...

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
    ) -> PublishResult: ...

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
    ) -> PublishResult: ...

    # ----- Analytics (Faz 5) --------------------------------------------
    # Returns raw analytics dicts (NOT PublishResult) — the shapes are
    # backend-stable and the tool layer already consumes them directly.

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
    ) -> dict[str, Any]: ...
