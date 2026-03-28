"""Late API base client with shared HTTP logic, accounts, and analytics."""

from __future__ import annotations

from typing import Any, Literal

import httpx


class _LateBase:
    """Base class with HTTP configuration, account management, and analytics."""

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
            params["postId"] = post_id
        else:
            params["profileId"] = self.account_id
            params["limit"] = max(1, min(limit, 100))
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

            if post_id:
                return {
                    "success": True,
                    "post": data,
                }

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
        return await self.get_analytics(post_id=post_id)

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
