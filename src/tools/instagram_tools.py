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
    limit: int = 20,
    page: int = 1,
    sort_by: str = "date",
    order: str = "desc",
) -> dict[str, Any]:
    """
    Fetch Instagram post analytics via Late API.

    Retrieves posts and their performance metrics including
    impressions, reach, likes, comments, shares, saves, clicks, views, and engagement rate.

    NOTE: Analytics data is cached and refreshed at most once per hour by Late API.

    Args:
        instagram_id: Late account ID (acc_xxxxx) from business profile.
        date_from: Start date filter (YYYY-MM-DD format, optional).
        date_to: End date filter (YYYY-MM-DD format, optional).
        limit: Posts per page (default 20, max 100).
        page: Page number (default 1).
        sort_by: Sort by "date" or "engagement" (default: "date").
        order: Sort direction "asc" or "desc" (default: "desc").

    Returns:
        dict with:
        - success: bool
        - media_items: list of posts with analytics
        - pagination: {total, page, limit, total_pages}
        - summary: aggregated statistics (totals, averages, top performers)
    """
    try:
        late = get_late_client(instagram_id)

        # Validate sort_by parameter
        valid_sort_by = sort_by if sort_by in ("date", "engagement") else "date"
        valid_order = order if order in ("asc", "desc") else "desc"

        result = await late.get_analytics(
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            page=page,
            sort_by=valid_sort_by,
            order=valid_order,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "media_items": [],
                "pagination": {"total": 0, "page": 1, "limit": limit, "total_pages": 0},
            }

        posts = result.get("posts", [])
        pagination = result.get("pagination", {})

        # Transform to standard format
        media_items = []
        for post in posts:
            analytics = post.get("analytics", {})
            media_items.append({
                # IMPORTANT: ID field contains Late's internal ID (MongoDB ObjectId),
                # NOT Instagram's native media ID! Do NOT use this for Firestore matching.
                "id": post.get("postId"),
                # Late's scheduled post ID (if the post was scheduled via Late)
                "late_post_id": post.get("latePostId"),
                # USE THIS FOR MATCHING: platform_post_url matches Firestore's permalink field
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
                    "clicks": analytics.get("clicks", 0),
                    "views": analytics.get("views", 0),
                    "engagement_rate": analytics.get("engagementRate", 0),
                },
                "is_external": post.get("isExternal", False),
            })

        # Calculate summary
        summary = _calculate_summary(media_items)

        return {
            "success": True,
            "media_items": media_items,
            "pagination": {
                "total": pagination.get("total", len(media_items)),
                "page": pagination.get("page", page),
                "limit": pagination.get("limit", limit),
                "total_pages": pagination.get("total_pages", 1),
            },
            "summary": summary,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch insights: {type(e).__name__}: {e}",
            "media_items": [],
            "pagination": {"total": 0, "page": 1, "limit": limit, "total_pages": 0},
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
    total_clicks = 0
    total_views = 0
    total_engagement = 0.0

    for item in media_items:
        metrics = item.get("metrics", {})
        total_impressions += metrics.get("impressions", 0) or 0
        total_reach += metrics.get("reach", 0) or 0
        total_likes += metrics.get("likes", 0) or 0
        total_comments += metrics.get("comments", 0) or 0
        total_shares += metrics.get("shares", 0) or 0
        total_saves += metrics.get("saves", 0) or 0
        total_clicks += metrics.get("clicks", 0) or 0
        total_views += metrics.get("views", 0) or 0
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
        "total_clicks": total_clicks,
        "total_views": total_views,
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


@function_tool
async def get_post_analytics(
    instagram_id: str,
    post_id: str,
) -> dict[str, Any]:
    """
    Fetch detailed analytics for a specific Instagram post.

    Use this when you need complete metrics for a single post.
    The API accepts both Late Post ID and External Post ID - it auto-resolves.

    Args:
        instagram_id: Late account ID (acc_xxxxx) from business profile.
        post_id: The post ID (Late ID like "65f1c0a9..." or External ID).

    Returns:
        dict with:
        - success: bool
        - post: {
            id, late_post_id, status, content, platform_post_url,
            scheduled_for, published_at, is_external,
            metrics: {impressions, reach, likes, comments, shares,
                      clicks, views, saves, engagement_rate, last_updated}
          }
        - platform_analytics: Per-platform breakdown (for cross-posted content)
    """
    try:
        late = get_late_client(instagram_id)
        result = await late.get_analytics(post_id=post_id)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
            }

        post = result.get("post", {})
        analytics = post.get("analytics", {})

        return {
            "success": True,
            "post": {
                "id": post.get("postId"),
                "late_post_id": post.get("latePostId"),
                "status": post.get("status"),
                "content": post.get("content"),
                "platform_post_url": post.get("platformPostUrl"),
                "scheduled_for": post.get("scheduledFor"),
                "published_at": post.get("publishedAt"),
                "is_external": post.get("isExternal", False),
                "metrics": {
                    "impressions": analytics.get("impressions", 0),
                    "reach": analytics.get("reach", 0),
                    "likes": analytics.get("likes", 0),
                    "comments": analytics.get("comments", 0),
                    "shares": analytics.get("shares", 0),
                    "saves": analytics.get("saves", 0),
                    "clicks": analytics.get("clicks", 0),
                    "views": analytics.get("views", 0),
                    "engagement_rate": analytics.get("engagementRate", 0),
                    "last_updated": analytics.get("lastUpdated"),
                },
            },
            "platform_analytics": post.get("platformAnalytics", []),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch post analytics: {type(e).__name__}: {e}",
        }


def get_instagram_tools() -> list:
    """Return list of Instagram insight tools for marketing agent."""
    return [get_instagram_insights, get_post_analytics]


__all__ = ["get_instagram_insights", "get_post_analytics", "get_instagram_tools"]
