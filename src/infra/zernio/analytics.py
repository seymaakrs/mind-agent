"""Analytics endpoints on Zernio (`/v1/analytics`, `/v1/accounts`).

Mirrors the surface ``LateBase`` exposes (Zernio and Late share the same
query shape; the same ``profileId`` value is valid on both backends).
"""
from __future__ import annotations

from typing import Any


class _AnalyticsMixin:
    """``/v1/analytics`` and ``/v1/accounts`` operations."""

    async def get_analytics(
        self,
        *,
        post_id: str | None = None,
        profile_id: str | None = None,
        account_id: str | None = None,
        platform: str | None = "instagram",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        page: int = 1,
        sort_by: str = "date",
        order: str = "desc",
        source: str | None = None,
    ) -> dict[str, Any]:
        """List-mode or single-post analytics.

        With ``post_id`` returns one ``AnalyticsSinglePostResponse``;
        otherwise returns ``{posts: [...], pagination: {...}}``.
        """
        params: dict[str, Any] = {}
        if post_id:
            params["postId"] = post_id
        else:
            if profile_id:
                params["profileId"] = profile_id
            if account_id:
                params["accountId"] = account_id
            params["limit"] = max(1, min(limit, 100))
            params["page"] = max(1, page)
            params["sortBy"] = sort_by
            params["order"] = order
            if date_from:
                params["fromDate"] = date_from
            if date_to:
                params["toDate"] = date_to
            if source:
                params["source"] = source
        if platform:
            params["platform"] = platform
        return await self._get("/analytics", params=params)

    async def get_post_analytics(self, post_id: str) -> dict[str, Any]:
        """Single-post analytics by Zernio post _id or external post id."""
        return await self.get_analytics(post_id=post_id)

    async def get_accounts(self, platform: str | None = None) -> dict[str, Any]:
        """List connected social accounts (optionally filtered by platform)."""
        params: dict[str, Any] = {}
        if platform:
            params["platform"] = platform
        return await self._get("/accounts", params=params)
