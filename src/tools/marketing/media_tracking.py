from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from agents import function_tool

from src.infra.firebase_client import get_document_client


def _normalize_post_url(url: str | None) -> str | None:
    """
    Normalize an Instagram post URL so insights and saved posts compare equal.

    Strips the scheme/host (so http vs https or www. vs no-www. doesn't matter),
    drops query strings/fragments, and removes a trailing slash. Returns the
    raw path (e.g. "/p/ABC123") which is the part Instagram actually owns.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return None
    path = parsed.path or ""
    if path.endswith("/"):
        path = path[:-1]
    return path or None


# =============================================================================
# Instagram Post Tracking
# =============================================================================

@function_tool(strict_mode=False)
async def save_instagram_post(
    business_id: str,
    instagram_media_id: str,
    content_type: str,
    topic: str,
    caption: str,
    our_media_path: str,
    theme: str | None = None,
    hashtags: list[str] | None = None,
    permalink: str | None = None,
) -> dict[str, Any]:
    """
    Save a record of a posted Instagram content.

    Args:
        business_id: Business ID.
        instagram_media_id: Instagram media ID returned after posting.
        content_type: "image" or "reels".
        topic: Content topic.
        caption: Posted caption.
        our_media_path: Firebase Storage path of our generated media.
        theme: Optional theme/campaign.
        hashtags: List of hashtags used.
        permalink: Instagram post URL (from Late API platform_post_url).

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/instagram_posts")

        post_data = {
            "posted_at": datetime.now().isoformat(),
            "content_type": content_type,
            "topic": topic,
            "theme": theme,
            "caption": caption,
            "hashtags": hashtags or [],
            "our_media_path": our_media_path,
            "permalink": permalink,
        }

        doc_client.set_document(instagram_media_id, post_data)

        return {
            "success": True,
            "instagram_media_id": instagram_media_id,
            "message": "Instagram post record saved",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_instagram_posts(
    business_id: str,
    limit: int = 20,
    topic_filter: str | None = None,
) -> dict[str, Any]:
    """
    Get saved Instagram post records for a business.

    Args:
        business_id: Business ID.
        limit: Maximum number of posts to return.
        topic_filter: Filter by topic (optional).

    Returns:
        dict with post records.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/instagram_posts")

        posts = doc_client.list_documents(limit=limit)

        if topic_filter:
            posts = [p for p in posts if p.get("topic") == topic_filter]

        posts.sort(key=lambda x: x.get("posted_at", ""), reverse=True)

        return {
            "success": True,
            "posts": posts,
            "count": len(posts),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "posts": []}


@function_tool
async def get_post_by_instagram_id(
    business_id: str,
    instagram_media_id: str,
) -> dict[str, Any]:
    """
    Get a specific Instagram post record by its Instagram media ID.

    Args:
        business_id: Business ID.
        instagram_media_id: Instagram media ID.

    Returns:
        dict with post record or not found message.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/instagram_posts")

        post = doc_client.get_document(instagram_media_id)

        if post:
            return {
                "success": True,
                "found": True,
                "post": post,
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": f"No record found for Instagram media ID: {instagram_media_id}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Insights ↔ Saved Post Matching
# =============================================================================

async def _match_insights_with_posts_impl(
    business_id: str,
    insights: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure async logic for match_insights_with_posts (kept undecorated for unit tests)."""
    try:
        doc_client = get_document_client(f"businesses/{business_id}/instagram_posts")
        saved_posts = doc_client.list_documents(limit=200)

        url_to_post: dict[str, dict[str, Any]] = {}
        for post in saved_posts:
            normalized = _normalize_post_url(post.get("permalink"))
            if normalized:
                url_to_post[normalized] = post

        matched: list[dict[str, Any]] = []
        unmatched: list[dict[str, Any]] = []

        for insight in insights:
            normalized_url = _normalize_post_url(insight.get("platform_post_url"))
            saved = url_to_post.get(normalized_url) if normalized_url else None

            if saved is not None:
                matched.append({
                    **insight,
                    "saved_post": saved,
                    "topic": saved.get("topic"),
                    "theme": saved.get("theme"),
                })
            else:
                unmatched.append(insight)

        match_rate = len(matched) / len(insights) if insights else 0.0

        return {
            "success": True,
            "matched": matched,
            "unmatched": unmatched,
            "match_rate": round(match_rate, 4),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "matched": [],
            "unmatched": insights,
            "match_rate": 0.0,
        }


@function_tool(strict_mode=False)
async def match_insights_with_posts(
    business_id: str,
    insights: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Join Late Analytics insights with Firestore-saved Instagram posts via URL.

    Late Analytics returns posts identified by an internal Late ID, while our
    Firestore records use Instagram's native media id. The reliable shared key
    is the post URL: insight.platform_post_url ↔ saved_post.permalink. URLs
    are normalized so trailing slashes, query params, and http/https variants
    don't break the join.

    Args:
        business_id: Business ID whose Instagram posts to load.
        insights: List of insight dicts from get_instagram_insights, each
            expected to carry a "platform_post_url" field.

    Returns:
        dict with:
        - success: bool
        - matched: list of insights with topic/theme/saved_post fields merged in
        - unmatched: list of insights with no matching saved post
        - match_rate: float in [0.0, 1.0]; 0.0 if insights list is empty
    """
    return await _match_insights_with_posts_impl(business_id, insights)


# =============================================================================
# YouTube Video Tracking
# =============================================================================

@function_tool(strict_mode=False)
async def save_youtube_video(
    business_id: str,
    youtube_video_id: str,
    title: str,
    description: str,
    our_media_path: str,
    video_url: str | None = None,
    visibility: str = "public",
    tags: list[str] | None = None,
    topic: str | None = None,
    thumbnail_url: str | None = None,
    published_at: str | None = None,
) -> dict[str, Any]:
    """
    Save a record of a posted YouTube video.

    Args:
        business_id: Business ID.
        youtube_video_id: YouTube video ID returned after posting.
        title: Video title.
        description: Video description.
        our_media_path: Firebase Storage path of our generated video.
        video_url: YouTube video URL (permalink).
        visibility: Video visibility (public, unlisted, private).
        tags: List of tags used.
        topic: Content topic (optional).
        thumbnail_url: Custom thumbnail URL if used.
        published_at: When the video was published.

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/youtube_videos")

        video_data = {
            "posted_at": datetime.now().isoformat(),
            "title": title,
            "description": description,
            "our_media_path": our_media_path,
            "video_url": video_url,
            "visibility": visibility,
            "tags": tags or [],
            "topic": topic,
            "thumbnail_url": thumbnail_url,
            "published_at": published_at,
        }

        doc_client.set_document(youtube_video_id, video_data)

        return {
            "success": True,
            "youtube_video_id": youtube_video_id,
            "message": "YouTube video record saved",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_youtube_videos(
    business_id: str,
    limit: int = 20,
    topic_filter: str | None = None,
) -> dict[str, Any]:
    """
    Get saved YouTube video records for a business.

    Args:
        business_id: Business ID.
        limit: Maximum number of videos to return.
        topic_filter: Filter by topic (optional).

    Returns:
        dict with video records.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/youtube_videos")

        videos = doc_client.list_documents(limit=limit)

        if topic_filter:
            videos = [v for v in videos if v.get("topic") == topic_filter]

        videos.sort(key=lambda x: x.get("posted_at", ""), reverse=True)

        return {
            "success": True,
            "videos": videos,
            "count": len(videos),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "videos": []}


@function_tool
async def get_youtube_video_by_id(
    business_id: str,
    youtube_video_id: str,
) -> dict[str, Any]:
    """
    Get a specific YouTube video record by its video ID.

    Args:
        business_id: Business ID.
        youtube_video_id: YouTube video ID.

    Returns:
        dict with video record or not found message.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/youtube_videos")

        video = doc_client.get_document(youtube_video_id)

        if video:
            return {
                "success": True,
                "found": True,
                "video": video,
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": f"No record found for YouTube video ID: {youtube_video_id}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
