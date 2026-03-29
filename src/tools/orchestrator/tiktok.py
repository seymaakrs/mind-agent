from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.errors import classify_error, classify_late_response
from src.infra.firebase_client import get_document_client
from src.infra.late_client import get_late_client


@function_tool(
    name_override="post_carousel_on_tiktok",
    description_override=(
        "Post a carousel (photo slideshow) to TikTok via Late API.\n\n"
        "Automatically fetches tiktok_account_id from the business profile in Firebase.\n\n"
        "REQUIRED PARAMETERS:\n"
        "1. media_items: List of 2-35 image objects. EACH object MUST have:\n"
        '   - "url": Full public URL (JPEG/PNG/WebP, max 20MB each)\n'
        '   - "type": "image"\n'
        "2. content: Carousel title (max 90 chars). Hashtags/URLs auto-cleaned by TikTok.\n"
        "3. privacy_level: Creator's allowed privacy value (e.g. PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY)\n"
        "4. business_id: Business ID to fetch tiktok_account_id from Firebase\n\n"
        "OPTIONAL PARAMETERS:\n"
        "- description: Long caption (max 4000 chars). content is the title, description is the real caption.\n"
        "- allow_comment: Allow comments (default: true)\n"
        "- photo_cover_index: Which photo is cover (0-indexed, default: 0)\n"
        "- auto_add_music: TikTok auto-adds music (carousel only)\n"
        "- video_made_with_ai: AI disclosure flag\n"
        "- draft: Send to Creator Inbox, don't publish directly\n"
        "- commercial_content_type: Commercial content disclosure\n\n"
        "NOTE: allow_duet and allow_stitch are NOT applicable for carousel posts (video only)."
    ),
    strict_mode=False,
)
async def post_carousel_on_tiktok(
    media_items: list[dict],
    content: str,
    privacy_level: str,
    business_id: str,
    description: str | None = None,
    allow_comment: bool = True,
    photo_cover_index: int | None = None,
    auto_add_music: bool | None = None,
    video_made_with_ai: bool | None = None,
    draft: bool | None = None,
    commercial_content_type: str | None = None,
) -> dict[str, Any]:
    """
    Post a carousel to TikTok via Late API.

    Args:
        media_items: List of image items [{"type": "image", "url": "..."}, ...] (2-35 items).
        content: Carousel title (max 90 chars).
        privacy_level: TikTok privacy level.
        business_id: Business ID to fetch tiktok_account_id from Firebase.
        description: Long caption (max 4000 chars, optional).
        allow_comment: Allow comments (default True).
        photo_cover_index: Cover photo index, 0-based (optional).
        auto_add_music: Let TikTok auto-add music (optional).
        video_made_with_ai: AI disclosure flag (optional).
        draft: Send to Creator Inbox instead of publishing (optional).
        commercial_content_type: Commercial content disclosure (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if len(content) > 90:
            return {
                "success": False,
                "error": f"Content (title) exceeds 90 characters ({len(content)} chars)",
            }

        if description and len(description) > 4000:
            return {
                "success": False,
                "error": f"Description exceeds 4000 characters ({len(description)} chars)",
            }

        if len(media_items) < 2:
            return {
                "success": False,
                "error": "TikTok carousel requires at least 2 media items",
            }

        if len(media_items) > 35:
            return {
                "success": False,
                "error": "TikTok carousel cannot have more than 35 media items",
            }

        # Validate each media item
        for i, item in enumerate(media_items):
            if not isinstance(item, dict):
                return {
                    "success": False,
                    "error": f"media_items[{i}] must be a dict, got {type(item).__name__}",
                }
            url = item.get("url")
            if not url:
                return {
                    "success": False,
                    "error": f"media_items[{i}] missing required 'url' field",
                }
            if not url.startswith("http"):
                return {
                    "success": False,
                    "error": f"media_items[{i}] has invalid URL '{url}'. URL must start with http:// or https://",
                }

        # Validate photo_cover_index
        if photo_cover_index is not None and (photo_cover_index < 0 or photo_cover_index >= len(media_items)):
            return {
                "success": False,
                "error": f"photo_cover_index ({photo_cover_index}) is out of range. Must be 0-{len(media_items) - 1}",
            }

        # --- Fetch tiktok_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        tiktok_account_id = business.get("tiktok_account_id")
        if not tiktok_account_id:
            return {
                "success": False,
                "error": f"No tiktok_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(tiktok_account_id)
        result = await late.post_tiktok_carousel(
            media_items=media_items,
            content=content,
            privacy_level=privacy_level,
            allow_comment=allow_comment,
            description=description,
            photo_cover_index=photo_cover_index,
            auto_add_music=auto_add_music,
            video_made_with_ai=video_made_with_ai,
            draft=draft,
            commercial_content_type=commercial_content_type,
        )

        if not result.get("success"):
            classified = classify_late_response(result, "late")
            classified["item_count"] = len(media_items)
            return classified

        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "carousel",
            "item_count": result.get("item_count"),
            "message": f"Successfully posted carousel with {result.get('item_count')} items to TikTok",
        }

    except Exception as exc:
        result = classify_error(exc, "late")
        result["item_count"] = len(media_items)
        return result


@function_tool(
    name_override="post_on_tiktok",
    description_override=(
        "Post a video to TikTok via Late API.\n\n"
        "Automatically fetches tiktok_account_id from the business profile in Firebase.\n\n"
        "REQUIRED PARAMETERS:\n"
        "1. video_url: Public URL of the video (MP4/MOV/WebM, max 4GB, 3s-10min)\n"
        "2. content: Video caption (max 2200 chars)\n"
        "3. privacy_level: Creator's allowed value (PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, SELF_ONLY)\n"
        "4. business_id: Business ID to fetch tiktok_account_id from Firebase\n\n"
        "OPTIONAL PARAMETERS:\n"
        "- allow_comment: Allow comments (default: true)\n"
        "- allow_duet: Allow duet (default: true). Video only.\n"
        "- allow_stitch: Allow stitch (default: true). Video only.\n"
        "- video_cover_timestamp_ms: Cover frame timestamp in ms (default: 1000 = 1st second)\n"
        "- video_made_with_ai: AI disclosure flag\n"
        "- draft: Send to Creator Inbox, don't publish directly\n"
        "- commercial_content_type: 'none', 'brand_organic', or 'brand_content'"
    ),
    strict_mode=False,
)
async def post_on_tiktok(
    video_url: str,
    content: str,
    privacy_level: str,
    business_id: str,
    allow_comment: bool = True,
    allow_duet: bool = True,
    allow_stitch: bool = True,
    video_cover_timestamp_ms: int | None = None,
    video_made_with_ai: bool | None = None,
    draft: bool | None = None,
    commercial_content_type: str | None = None,
) -> dict[str, Any]:
    """
    Post a video to TikTok via Late API.

    Args:
        video_url: Public URL of the video file.
        content: Video caption (max 2200 chars).
        privacy_level: TikTok privacy level.
        business_id: Business ID to fetch tiktok_account_id from Firebase.
        allow_comment: Allow comments (default True).
        allow_duet: Allow duet (default True).
        allow_stitch: Allow stitch (default True).
        video_cover_timestamp_ms: Cover frame timestamp in ms (optional).
        video_made_with_ai: AI disclosure flag (optional).
        draft: Send to Creator Inbox (optional).
        commercial_content_type: Commercial content disclosure (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if len(content) > 2200:
            return {
                "success": False,
                "error": f"Content (caption) exceeds 2200 characters ({len(content)} chars)",
            }

        if not video_url.startswith("http"):
            return {
                "success": False,
                "error": f"Invalid video URL '{video_url}'. URL must start with http:// or https://",
            }

        # --- Fetch tiktok_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        tiktok_account_id = business.get("tiktok_account_id")
        if not tiktok_account_id:
            return {
                "success": False,
                "error": f"No tiktok_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(tiktok_account_id)
        result = await late.post_tiktok_video(
            video_url=video_url,
            content=content,
            privacy_level=privacy_level,
            allow_comment=allow_comment,
            allow_duet=allow_duet,
            allow_stitch=allow_stitch,
            video_cover_timestamp_ms=video_cover_timestamp_ms,
            video_made_with_ai=video_made_with_ai,
            draft=draft,
            commercial_content_type=commercial_content_type,
        )

        if not result.get("success"):
            classified = classify_late_response(result, "late")
            classified.update({"video_url": video_url})
            return classified

        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "video",
            "message": "Successfully posted video to TikTok",
        }

    except Exception as exc:
        result = classify_error(exc, "late")
        result.update({"video_url": video_url})
        return result
