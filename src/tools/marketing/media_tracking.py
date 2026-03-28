from __future__ import annotations

from datetime import datetime
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


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
