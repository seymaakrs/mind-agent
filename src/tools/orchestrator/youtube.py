from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from agents import function_tool

from src.infra.errors import classify_error, classify_late_response
from src.infra.firebase_client import get_document_client
from src.infra.late_client import get_late_client


@function_tool(
    name_override="post_on_youtube",
    description_override=(
        "Post a video to YouTube via Late API. Automatically saves record to Firestore.\n\n"
        "REQUIRED:\n"
        "- video_url: Public URL of the video file\n"
        "- youtube_id: Late account ID from business profile (fetch_business result)\n"
        "- business_id: Business ID for Firestore record\n\n"
        "Optional Parameters:\n"
        "- title: Video title (max 100 characters)\n"
        "- description: Video description (max 5000 characters)\n"
        "- visibility: 'public', 'unlisted', or 'private' (default: public)\n"
        "- made_for_kids: COPPA compliance (default: false)\n"
        "- tags: List of tags (total 500 char limit)\n"
        "- thumbnail_url: Custom thumbnail (only for videos >3min)\n"
        "- first_comment: Pinned first comment (max 10000 chars)\n"
        "- scheduled_for: ISO datetime for scheduled upload\n"
        "- our_media_path: Firebase Storage path of source video (for tracking)"
    ),
    strict_mode=False,
)
async def post_on_youtube(
    video_url: str,
    youtube_id: str,
    business_id: str,
    title: str | None = None,
    description: str | None = None,
    visibility: Literal["public", "unlisted", "private"] = "public",
    made_for_kids: bool = False,
    tags: list[str] | None = None,
    thumbnail_url: str | None = None,
    first_comment: str | None = None,
    scheduled_for: str | None = None,
    our_media_path: str | None = None,
) -> dict[str, Any]:
    """
    Post a video to YouTube via Late API. Automatically saves record to Firestore.

    Args:
        video_url: Public URL of the video file.
        youtube_id: Late account ID (acc_xxxxx) from business profile.
        business_id: Business ID for Firestore record.
        title: Video title (max 100 chars, optional).
        description: Video description (max 5000 chars, optional).
        visibility: "public", "unlisted", or "private" (default: public).
        made_for_kids: COPPA compliance flag (default: False).
        tags: List of tags (total 500 char limit, optional).
        thumbnail_url: Custom thumbnail URL (only for videos >3min, optional).
        first_comment: Pinned first comment (max 10000 chars, optional).
        scheduled_for: ISO datetime for scheduled upload (optional).
        our_media_path: Firebase Storage path of source video (optional, for tracking).

    Returns:
        dict with success, video_id, and details.
    """
    try:
        # Validations
        if title and len(title) > 100:
            return {
                "success": False,
                "error": f"Title exceeds 100 characters ({len(title)} chars)",
            }

        if description and len(description) > 5000:
            return {
                "success": False,
                "error": f"Description exceeds 5000 characters ({len(description)} chars)",
            }

        if tags:
            total_tag_chars = sum(len(tag) for tag in tags)
            if total_tag_chars > 500:
                return {
                    "success": False,
                    "error": f"Tags exceed 500 character limit ({total_tag_chars} chars)",
                }

        if first_comment and len(first_comment) > 10000:
            return {
                "success": False,
                "error": f"First comment exceeds 10000 characters ({len(first_comment)} chars)",
            }

        late = get_late_client(youtube_id)
        result = await late.post_youtube_video(
            video_url=video_url,
            title=title,
            description=description,
            visibility=visibility,
            made_for_kids=made_for_kids,
            tags=tags,
            thumbnail_url=thumbnail_url,
            first_comment=first_comment,
            scheduled_for=scheduled_for,
        )

        if not result.get("success"):
            classified = classify_late_response(result, "late")
            classified.update({"video_url": video_url})
            return classified

        # Extract response data
        youtube_video_id = result.get("platform_post_id")
        youtube_video_url = result.get("platform_post_url")
        published_at = result.get("published_at")

        # Auto-save to Firestore
        if youtube_video_id:
            try:
                doc_client = get_document_client(
                    f"businesses/{business_id}/youtube_videos"
                )
                video_data = {
                    "posted_at": datetime.now().isoformat(),
                    "title": title or "",
                    "description": description or "",
                    "our_media_path": our_media_path or "",
                    "video_url": youtube_video_url,
                    "visibility": visibility,
                    "tags": tags or [],
                    "thumbnail_url": thumbnail_url,
                    "published_at": published_at,
                }
                doc_client.set_document(youtube_video_id, video_data)
            except Exception:
                # Don't fail the whole operation if Firestore save fails
                pass

        return {
            "success": True,
            "video_id": youtube_video_id,
            "late_post_id": result.get("post_id"),
            "video_url": youtube_video_url,
            "status": result.get("status"),
            "published_at": published_at,
            "message": "Successfully posted video to YouTube",
        }

    except Exception as exc:
        result = classify_error(exc, "late")
        result.update({"video_url": video_url})
        return result
