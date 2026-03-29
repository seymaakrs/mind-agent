from __future__ import annotations

from typing import Any, Literal

from agents import function_tool

from src.infra.errors import classify_error, classify_late_response
from src.infra.late_client import get_late_client


# --- Instagram aspect ratio constants ---
INSTAGRAM_VALID_RATIOS = {"4:5", "1:1", "1.91:1", "16:9", "4:3"}
INSTAGRAM_INVALID_RATIOS = {"3:4", "9:16"}  # Story/Reels only, not feed
INSTAGRAM_MIN_RATIO = 0.8   # 4:5
INSTAGRAM_MAX_RATIO = 1.91  # 1.91:1


def _parse_ratio(ratio_str: str) -> float | None:
    """Parse 'W:H' string to float. Returns None if unparseable."""
    try:
        parts = ratio_str.split(":")
        return float(parts[0]) / float(parts[1])
    except (ValueError, IndexError, ZeroDivisionError):
        return None


@function_tool(
    name_override="post_on_instagram",
    description_override=(
        "Post content to Instagram via Late API (feed post, reel, or story). "
        "Requires instagram_id from business profile. "
        "\n\n"
        "IMPORTANT: You MUST provide instagram_id from the business profile. "
        "This is found in the fetch_business result under 'instagram_id' field."
        "\n\n"
        "For STORIES:\n"
        "- Set is_story=True\n"
        "- Caption is ignored (Instagram Stories don't support captions)\n"
        "- Recommended aspect ratio: 9:16 (1080x1920)\n"
        "- Stories disappear after 24 hours"
    ),
    strict_mode=False,
)
async def post_on_instagram(
    file_url: str,
    caption: str,
    content_type: Literal["image", "video"],
    instagram_id: str,
    thumbnail_url: str | None = None,
    first_comment: str | None = None,
    is_story: bool = False,
) -> dict[str, Any]:
    """
    Post content to Instagram via Late API.

    Args:
        file_url: Public URL of the file to post.
        caption: Post caption (ignored for stories).
        content_type: Type of content ("image" or "video").
        instagram_id: Late account ID (acc_xxxxx) from business profile.
        thumbnail_url: Custom thumbnail URL for Reels (optional, ignored for stories).
        first_comment: First comment to add after posting (optional, ignored for stories).
        is_story: If True, post as Instagram Story instead of feed post.

    Returns:
        dict with success, post_id, and details.
    """
    try:
        late = get_late_client(instagram_id)
        result = await late.post_media(
            media_url=file_url,
            caption=caption,
            media_type=content_type,
            thumbnail_url=thumbnail_url,
            first_comment=first_comment,
            is_story=is_story,
        )

        if not result.get("success"):
            classified = classify_late_response(result, "late")
            classified.update({"file_url": file_url, "content_type": content_type, "is_story": is_story})
            return classified

        post_type = "story" if is_story else content_type
        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": post_type,
            "is_story": is_story,
            "message": f"Successfully posted {post_type} to Instagram",
        }

    except Exception as exc:
        result = classify_error(exc, "late")
        result.update({"file_url": file_url, "content_type": content_type, "is_story": is_story})
        return result


@function_tool(
    name_override="post_carousel_on_instagram",
    description_override=(
        "Post a carousel (multiple images/videos) to Instagram via Late API.\n\n"
        "REQUIRED PARAMETERS:\n"
        "1. media_items: List of 2-10 media objects. EACH object MUST have:\n"
        '   - "url": Full public URL (e.g., "https://storage.googleapis.com/...")\n'
        '   - "type": Either "image" or "video"\n'
        '   Example: [{"url": "https://storage.googleapis.com/bucket/img1.png", "type": "image"}, '
        '{"url": "https://storage.googleapis.com/bucket/img2.png", "type": "image"}]\n'
        "2. caption: Post caption text\n"
        "3. instagram_id: From business profile\n\n"
        "DO NOT include business_id - it is NOT a parameter of this tool."
    ),
    strict_mode=False,
)
async def post_carousel_on_instagram(
    media_items: list[dict],
    caption: str,
    instagram_id: str,
    first_comment: str | None = None,
) -> dict[str, Any]:
    """
    Post a carousel to Instagram via Late API.

    Args:
        media_items: List of media items. Each item must have:
                     - url (required): Public URL of the media
                     - type (required): "image" or "video"
                     - aspect_ratio (recommended): e.g. "1:1", "4:5", "16:9"

                     IMPORTANT: All items must have the same aspect ratio.
                     The first item's ratio determines the carousel display.
        caption: Post caption.
        instagram_id: Late account ID (acc_xxxxx) from business profile.
        first_comment: First comment to add after posting (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        if len(media_items) < 2:
            return {"success": False, "error": "Carousel requires at least 2 media items"}

        if len(media_items) > 10:
            return {"success": False, "error": "Carousel cannot have more than 10 media items"}

        # Validate media_items structure
        aspect_ratios_found = []
        for i, item in enumerate(media_items):
            if not isinstance(item, dict):
                return {"success": False, "error": f"media_items[{i}] must be a dict, got {type(item).__name__}"}
            url = item.get("url")
            if not url:
                return {"success": False, "error": f"media_items[{i}] missing required 'url' field. Each item must have {{'url': 'https://...', 'type': 'image'|'video'}}"}
            if not url.startswith("http"):
                return {"success": False, "error": f"media_items[{i}] has invalid URL '{url}'. URL must start with http:// or https://"}
            if item.get("type") not in ("image", "video", None):
                return {"success": False, "error": f"media_items[{i}] has invalid type '{item.get('type')}'. Must be 'image' or 'video'"}

            # Collect aspect ratios for validation
            if item.get("aspect_ratio"):
                aspect_ratios_found.append(item["aspect_ratio"])

        # --- Instagram aspect ratio validation ---
        aspect_ratio_warning = None
        if aspect_ratios_found:
            if len(aspect_ratios_found) != len(media_items):
                return {
                    "success": False,
                    "error": f"Aspect ratio must be specified for all items or none. Found {len(aspect_ratios_found)}/{len(media_items)} items with aspect_ratio."
                }

            first_ratio = aspect_ratios_found[0]
            mismatched = [i for i, r in enumerate(aspect_ratios_found) if r != first_ratio]
            if mismatched:
                return {
                    "success": False,
                    "error": f"All carousel items must have the same aspect ratio. First item has '{first_ratio}', but item(s) {mismatched} have different ratios. Instagram requires uniform aspect ratios in carousels."
                }

            # Validate that the ratio is Instagram-feed-compatible
            if first_ratio in INSTAGRAM_INVALID_RATIOS:
                return {
                    "success": False,
                    "error": (
                        f"Aspect ratio '{first_ratio}' is not valid for Instagram feed posts. "
                        f"Instagram feed accepts ratios between 4:5 (0.8) and 1.91:1. "
                        f"'{first_ratio}' is a Story/Reels format. Use '4:5' for portrait feed posts."
                    ),
                }
            numeric = _parse_ratio(first_ratio)
            if numeric is not None and (numeric < INSTAGRAM_MIN_RATIO - 0.01 or numeric > INSTAGRAM_MAX_RATIO + 0.01):
                return {
                    "success": False,
                    "error": (
                        f"Aspect ratio '{first_ratio}' ({numeric:.2f}) is outside Instagram's allowed range "
                        f"({INSTAGRAM_MIN_RATIO}–{INSTAGRAM_MAX_RATIO}). Use '4:5' for portrait or '1:1' for square."
                    ),
                }
        else:
            aspect_ratio_warning = "WARNING: No aspect_ratio specified for carousel items. All items must have the same aspect ratio for proper display. First item's ratio determines the carousel."

        # Post carousel via Late API
        late = get_late_client(instagram_id)
        result = await late.post_carousel(
            media_items=media_items,
            caption=caption,
            first_comment=first_comment,
        )

        if not result.get("success"):
            classified = classify_late_response(result, "late")
            classified["item_count"] = len(media_items)
            return classified

        response = {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "carousel",
            "item_count": result.get("item_count"),
            "message": f"Successfully posted carousel with {result.get('item_count')} items to Instagram",
        }

        if aspect_ratio_warning:
            response["warning"] = aspect_ratio_warning

        return response

    except Exception as exc:
        result = classify_error(exc, "late")
        result["item_count"] = len(media_items)
        return result
