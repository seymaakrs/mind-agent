"""Instagram insights tool using Late API."""

from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.late_client import get_late_client


@function_tool
async def get_instagram_insights(
    instagram_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Fetch Instagram post analytics via Late API.

    Retrieves posts and their performance metrics including
    impressions, reach, likes, comments, shares, saves, and engagement rate.

    Args:
        instagram_id: Late account ID (acc_xxxxx) from business profile.
        date_from: Start date filter (YYYY-MM-DD format, optional).
        date_to: End date filter (YYYY-MM-DD format, optional).
        limit: Maximum number of posts to return (default 10).

    Returns:
        dict with:
        - success: bool
        - media_items: list of posts with analytics
        - summary: aggregated statistics (totals, averages, top performers)
    """
    try:
        late = get_late_client(instagram_id)
        result = await late.get_analytics(date_from=date_from, date_to=date_to)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "media_items": [],
            }

        posts = result.get("posts", [])

        # Apply limit
        posts = posts[:limit]

        # Transform to standard format
        media_items = []
        for post in posts:
            analytics = post.get("analytics", {})
            media_items.append({
                "id": post.get("postId"),
                "platform_post_url": post.get("platformPostUrl"),
                "content": post.get("content", "")[:100] if post.get("content") else None,
                "published_at": post.get("publishedAt"),
                "status": post.get("status"),
                "metrics": {
                    "impressions": analytics.get("impressions", 0),
                    "reach": analytics.get("reach", 0),
                    "likes": analytics.get("likes", 0),
                    "comments": analytics.get("comments", 0),
                    "shares": analytics.get("shares", 0),
                    "saves": analytics.get("saves", 0),
                    "engagement_rate": analytics.get("engagementRate", 0),
                },
                "is_external": post.get("isExternal", False),
            })

        # Calculate summary
        summary = _calculate_summary(media_items)

        return {
            "success": True,
            "media_items": media_items,
            "summary": summary,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch insights: {type(e).__name__}: {e}",
            "media_items": [],
        }


def _calculate_summary(media_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate summary statistics from media items."""
    if not media_items:
        return {}

    total_impressions = 0
    total_reach = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_saves = 0
    total_engagement = 0.0

    for item in media_items:
        metrics = item.get("metrics", {})
        total_impressions += metrics.get("impressions", 0) or 0
        total_reach += metrics.get("reach", 0) or 0
        total_likes += metrics.get("likes", 0) or 0
        total_comments += metrics.get("comments", 0) or 0
        total_shares += metrics.get("shares", 0) or 0
        total_saves += metrics.get("saves", 0) or 0
        total_engagement += metrics.get("engagement_rate", 0) or 0

    count = len(media_items)

    summary = {
        "total_media_count": count,
        "total_impressions": total_impressions,
        "total_reach": total_reach,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_saves": total_saves,
        "avg_impressions": round(total_impressions / count, 2) if count else 0,
        "avg_reach": round(total_reach / count, 2) if count else 0,
        "avg_likes": round(total_likes / count, 2) if count else 0,
        "avg_engagement_rate": round(total_engagement / count, 2) if count else 0,
    }

    # Find top performing content
    if media_items:
        top_by_reach = max(media_items, key=lambda x: x.get("metrics", {}).get("reach", 0) or 0)
        top_by_likes = max(media_items, key=lambda x: x.get("metrics", {}).get("likes", 0) or 0)

        summary["top_by_reach"] = {
            "id": top_by_reach["id"],
            "reach": top_by_reach.get("metrics", {}).get("reach"),
            "url": top_by_reach.get("platform_post_url"),
        }
        summary["top_by_likes"] = {
            "id": top_by_likes["id"],
            "likes": top_by_likes.get("metrics", {}).get("likes"),
            "url": top_by_likes.get("platform_post_url"),
        }

    return summary


def get_instagram_tools() -> list:
    """Return list of Instagram insight tools for marketing agent."""
    return [get_instagram_insights]


__all__ = ["get_instagram_insights", "get_instagram_tools"]
