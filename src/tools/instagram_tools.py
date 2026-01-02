from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

from agents import function_tool


class InstagramInsightsInput(BaseModel):
    """Input schema for Instagram insights tool."""

    ig_user_id: str = Field(..., description="Instagram Business Account ID")
    access_token: str = Field(..., description="Instagram Graph API access token")
    limit: int = Field(default=10, description="Number of recent media items to fetch (max 50)")
    since: str | None = Field(default=None, description="ISO date string - only fetch media after this date")
    include_reels_watch_time: bool = Field(default=True, description="Include Reels-specific watch time metrics")
    include_raw: bool = Field(default=False, description="Include raw API responses in output")
    api_version: str = Field(default="v23.0", description="Instagram Graph API version")


class InstagramInsightsClient:
    """Instagram Graph API client for fetching media insights."""

    BASE_URL = "https://graph.facebook.com"
    CONCURRENCY_LIMIT = 5
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0

    # Core metrics for all media types
    CORE_METRICS = ["reach", "views", "total_interactions", "shares", "saved"]

    # Additional metrics for Reels
    REELS_METRICS = ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]

    def __init__(self, access_token: str, api_version: str = "v23.0") -> None:
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"{self.BASE_URL}/{api_version}"

    async def get_user_media(
        self,
        ig_user_id: str,
        limit: int = 10,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent media items for a user.

        Args:
            ig_user_id: Instagram Business Account ID.
            limit: Number of items to fetch.
            since: ISO date string filter.

        Returns:
            List of media items with id, media_type, media_product_type, timestamp, permalink.
        """
        url = f"{self.base_url}/{ig_user_id}/media"
        params = {
            "fields": "id,media_type,media_product_type,timestamp,permalink,caption",
            "limit": min(limit, 50),
            "access_token": self.access_token,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"Failed to fetch media list: {response.status_code} - {error_detail}")

            data = response.json()
            media_items = data.get("data", [])

        # Filter by date if specified
        if since:
            # Parse since date and ensure it's timezone-aware (UTC)
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)

            filtered_items = []
            for item in media_items:
                # Parse Instagram timestamp (format: 2025-12-27T17:04:40+0000)
                ts = item["timestamp"].replace("+0000", "+00:00")
                item_dt = datetime.fromisoformat(ts)
                if item_dt.tzinfo is None:
                    item_dt = item_dt.replace(tzinfo=timezone.utc)

                if item_dt >= since_dt:
                    filtered_items.append(item)

            media_items = filtered_items

        return media_items

    async def get_media_insight(
        self,
        media_id: str,
        metric: str,
    ) -> dict[str, Any]:
        """
        Fetch a single insight metric for a media item.

        Args:
            media_id: Media ID.
            metric: Metric name (e.g., 'reach', 'views').

        Returns:
            Insight data or error dict.
        """
        url = f"{self.base_url}/{media_id}/insights"
        params = {
            "metric": metric,
            "access_token": self.access_token,
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        return {"success": True, "metric": metric, "data": data}

                    # Handle specific errors
                    error_data = response.json() if response.text else {}
                    error = error_data.get("error", {})

                    return {
                        "success": False,
                        "metric": metric,
                        "error": {
                            "code": error.get("code"),
                            "message": error.get("message", response.text),
                            "fbtrace_id": error.get("fbtrace_id"),
                        },
                    }

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    return {
                        "success": False,
                        "metric": metric,
                        "error": {"message": str(e)},
                    }

        return {"success": False, "metric": metric, "error": {"message": "Max retries exceeded"}}

    async def get_all_media_insights(
        self,
        media_item: dict[str, Any],
        include_reels_watch_time: bool = True,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """
        Fetch all insights for a single media item.

        Args:
            media_item: Media item dict with id, media_type, etc.
            include_reels_watch_time: Include Reels-specific metrics.
            include_raw: Include raw API responses.

        Returns:
            Media item with metrics attached.
        """
        media_id = media_item["id"]
        is_reels = media_item.get("media_product_type") == "REELS"

        # Determine which metrics to fetch
        metrics_to_fetch = self.CORE_METRICS.copy()
        if is_reels and include_reels_watch_time:
            metrics_to_fetch.extend(self.REELS_METRICS)

        # Fetch all metrics with concurrency limit
        semaphore = asyncio.Semaphore(self.CONCURRENCY_LIMIT)

        async def fetch_with_semaphore(metric: str) -> dict[str, Any]:
            async with semaphore:
                return await self.get_media_insight(media_id, metric)

        tasks = [fetch_with_semaphore(metric) for metric in metrics_to_fetch]
        results = await asyncio.gather(*tasks)

        # Process results
        metrics: dict[str, Any] = {}
        raw: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []

        for result in results:
            metric_name = result["metric"]

            if result["success"]:
                # Extract value from response
                data = result["data"].get("data", [])
                if data:
                    value = data[0].get("values", [{}])[0].get("value")
                    metrics[metric_name] = value

                    # For watch time metrics, add normalized seconds
                    if metric_name == "ig_reels_avg_watch_time" and value is not None:
                        metrics["ig_reels_avg_watch_time_ms"] = value
                        metrics["ig_reels_avg_watch_time_sec"] = round(value / 1000, 3)
                    elif metric_name == "ig_reels_video_view_total_time" and value is not None:
                        metrics["ig_reels_video_view_total_time_ms"] = value
                        metrics["ig_reels_video_view_total_time_sec"] = round(value / 1000, 3)

                if include_raw:
                    raw[metric_name] = result["data"]
            else:
                errors.append({
                    "media_id": media_id,
                    "metric": metric_name,
                    **result.get("error", {}),
                })

        # Build result
        result_item = {
            "id": media_id,
            "media_type": media_item.get("media_type"),
            "media_product_type": media_item.get("media_product_type"),
            "timestamp": media_item.get("timestamp"),
            "permalink": media_item.get("permalink"),
            "caption": media_item.get("caption", "")[:100] if media_item.get("caption") else None,
            "metrics": metrics,
        }

        if include_raw and raw:
            result_item["raw"] = raw

        if errors:
            result_item["errors"] = errors

        return result_item


async def _get_instagram_insights_async(
    ig_user_id: str,
    access_token: str,
    limit: int = 10,
    since: str | None = None,
    include_reels_watch_time: bool = True,
    include_raw: bool = False,
    api_version: str = "v23.0",
) -> dict[str, Any]:
    """
    Async implementation of Instagram insights fetching.
    """
    client = InstagramInsightsClient(access_token, api_version)

    # Step 1: Get media list
    try:
        media_items = await client.get_user_media(ig_user_id, limit, since)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch media list: {str(e)}",
            "media_items": [],
            "errors": [],
        }

    if not media_items:
        return {
            "success": True,
            "message": "No media items found",
            "media_items": [],
            "errors": [],
            "summary": {},
        }

    # Step 2: Get insights for each media item
    tasks = [
        client.get_all_media_insights(item, include_reels_watch_time, include_raw)
        for item in media_items
    ]
    results = await asyncio.gather(*tasks)

    # Step 3: Aggregate errors
    all_errors: list[dict[str, Any]] = []
    for result in results:
        if "errors" in result:
            all_errors.extend(result.pop("errors"))

    # Step 4: Calculate summary
    summary = _calculate_summary(results)

    return {
        "success": True,
        "media_items": results,
        "errors": all_errors,
        "summary": summary,
    }


def _calculate_summary(media_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate summary statistics from media items."""
    if not media_items:
        return {}

    total_reach = 0
    total_views = 0
    total_interactions = 0
    total_shares = 0
    total_saved = 0
    reels_count = 0
    total_watch_time_sec = 0.0

    for item in media_items:
        metrics = item.get("metrics", {})
        total_reach += metrics.get("reach", 0) or 0
        total_views += metrics.get("views", 0) or 0
        total_interactions += metrics.get("total_interactions", 0) or 0
        total_shares += metrics.get("shares", 0) or 0
        total_saved += metrics.get("saved", 0) or 0

        if item.get("media_product_type") == "REELS":
            reels_count += 1
            watch_time = metrics.get("ig_reels_avg_watch_time_sec", 0) or 0
            total_watch_time_sec += watch_time

    count = len(media_items)

    summary = {
        "total_media_count": count,
        "total_reach": total_reach,
        "total_views": total_views,
        "total_interactions": total_interactions,
        "total_shares": total_shares,
        "total_saved": total_saved,
        "avg_reach": round(total_reach / count, 2) if count else 0,
        "avg_views": round(total_views / count, 2) if count else 0,
        "avg_interactions": round(total_interactions / count, 2) if count else 0,
    }

    if reels_count > 0:
        summary["reels_count"] = reels_count
        summary["avg_reels_watch_time_sec"] = round(total_watch_time_sec / reels_count, 3)

    # Find top performing content
    if media_items:
        top_by_reach = max(media_items, key=lambda x: x.get("metrics", {}).get("reach", 0) or 0)
        top_by_views = max(media_items, key=lambda x: x.get("metrics", {}).get("views", 0) or 0)

        summary["top_by_reach"] = {
            "id": top_by_reach["id"],
            "reach": top_by_reach.get("metrics", {}).get("reach"),
            "permalink": top_by_reach.get("permalink"),
        }
        summary["top_by_views"] = {
            "id": top_by_views["id"],
            "views": top_by_views.get("metrics", {}).get("views"),
            "permalink": top_by_views.get("permalink"),
        }

    return summary


@function_tool
async def get_instagram_insights(
    ig_user_id: str,
    access_token: str,
    limit: int = 10,
    since: str | None = None,
    include_reels_watch_time: bool = True,
    include_raw: bool = False,
    api_version: str = "v23.0",
) -> dict[str, Any]:
    """
    Fetch Instagram media insights for a business account.

    Retrieves recent media items and their performance metrics including
    reach, views, total_interactions, shares, saved. For Reels, also
    fetches watch time metrics.

    Args:
        ig_user_id: Instagram Business Account ID.
        access_token: Instagram Graph API access token.
        limit: Number of recent media items to fetch (default 10, max 50).
        since: ISO date string - only fetch media after this date (optional).
        include_reels_watch_time: Include Reels-specific watch time metrics (default True).
        include_raw: Include raw API responses in output (default False).
        api_version: Instagram Graph API version (default "v23.0").

    Returns:
        dict with:
        - success: bool
        - media_items: list of media with metrics
        - errors: list of per-media/per-metric errors (fail-soft)
        - summary: aggregated statistics (totals, averages, top performers)
    """
    return await _get_instagram_insights_async(
        ig_user_id=ig_user_id,
        access_token=access_token,
        limit=limit,
        since=since,
        include_reels_watch_time=include_reels_watch_time,
        include_raw=include_raw,
        api_version=api_version,
    )


def get_instagram_tools() -> list:
    """Return list of Instagram insight tools for marketing agent."""
    return [get_instagram_insights]


__all__ = ["get_instagram_insights", "get_instagram_tools"]
