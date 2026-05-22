"""Posts endpoints on Zernio.

Wraps ``/v1/posts`` — multi-channel publish, list, get, retry, unpublish.
Zernio collapses what Late exposes as four separate platform clients into
one create-post call where the target list is part of the payload.

Faz 1 of the Late→Zernio migration (TODO Konfor #1). These methods are
additive — nothing in ``src/infra/late/`` or the tool layer is touched yet.
The PublisherClient abstraction in Faz 2 will sit on top of these.
"""
from __future__ import annotations

from typing import Any


# Supported platform identifiers per OpenAPI spec (componants.schemas.*PlatformData).
# Kept as a constant so callers can validate before hitting the API.
SUPPORTED_PLATFORMS = (
    "twitter",
    "threads",
    "facebook",
    "instagram",
    "linkedin",
    "pinterest",
    "youtube",
    "googlebusiness",
    "tiktok",
    "telegram",
    "snapchat",
    "reddit",
    "bluesky",
    "discord",
)

# Platforms that accept ``POST /v1/posts/{id}/unpublish`` (per OpenAPI enum).
UNPUBLISH_SUPPORTED = (
    "threads",
    "facebook",
    "twitter",
    "linkedin",
    "youtube",
    "pinterest",
    "reddit",
    "bluesky",
    "googlebusiness",
    "telegram",
)


class _PostsMixin:
    """``/v1/posts`` endpoints.

    Method names mirror the OpenAPI ``operationId`` (camelCase → snake_case)
    so future contributors can grep across the spec and the client.
    """

    async def create_post(
        self,
        *,
        content: str | None,
        platforms: list[dict[str, Any]],
        media_items: list[dict[str, str]] | None = None,
        scheduled_for: str | None = None,
        publish_now: bool = False,
        is_draft: bool = False,
        timezone: str = "UTC",
        title: str | None = None,
        tags: list[str] | None = None,
        hashtags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a post and (optionally) publish it.

        ``platforms`` is a list of ``{platform, accountId, ...}`` dicts. At
        least one entry is required when the post is not a draft (Zernio
        returns 400 otherwise). ``content`` may be ``None`` only when every
        platform entry sets ``customContent`` or when ``mediaItems`` is set.

        Exactly one of ``publish_now``, ``scheduled_for``, ``is_draft`` should
        be truthy. Zernio auto-classifies the post as a draft when none of
        them are set, so this method does not enforce mutual exclusion.
        """
        body: dict[str, Any] = {
            "platforms": platforms,
            "timezone": timezone,
        }
        if content is not None:
            body["content"] = content
        if media_items is not None:
            body["mediaItems"] = media_items
        if scheduled_for is not None:
            body["scheduledFor"] = scheduled_for
        if publish_now:
            body["publishNow"] = True
        if is_draft:
            body["isDraft"] = True
        if title is not None:
            body["title"] = title
        if tags is not None:
            body["tags"] = tags
        if hashtags is not None:
            body["hashtags"] = hashtags

        return await self._post("/posts", json=body)

    async def get_post(self, post_id: str) -> dict[str, Any]:
        """Fetch a single post by Zernio ``_id``."""
        return await self._get(f"/posts/{post_id}")

    async def list_posts(
        self,
        *,
        status: str | None = None,
        platform: str | None = None,
        profile_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        limit: int = 10,
        sort_by: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Paginated list of posts. ``status`` ∈ {draft, scheduled, published, failed}."""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            params["status"] = status
        if platform is not None:
            params["platform"] = platform
        if profile_id is not None:
            params["profileId"] = profile_id
        if date_from is not None:
            params["dateFrom"] = date_from
        if date_to is not None:
            params["dateTo"] = date_to
        if sort_by is not None:
            params["sortBy"] = sort_by
        if search is not None:
            params["search"] = search
        return await self._get("/posts", params=params)

    async def retry_post(self, post_id: str) -> dict[str, Any]:
        """Re-attempt a failed publish. Returns the updated post."""
        return await self._post(f"/posts/{post_id}/retry", json={})

    async def unpublish_post(self, post_id: str, platform: str) -> dict[str, Any]:
        """Remove a published post from one platform.

        Instagram, TikTok and Snapchat are intentionally rejected by Zernio
        (the upstream API does not expose deletion). We mirror that rule
        client-side so the caller fails fast with a clear message instead
        of a 400 round-trip.
        """
        if platform not in UNPUBLISH_SUPPORTED:
            raise ValueError(
                f"unpublish not supported for platform={platform!r}; "
                f"Zernio only allows: {', '.join(UNPUBLISH_SUPPORTED)}"
            )
        return await self._post(
            f"/posts/{post_id}/unpublish", json={"platform": platform}
        )
