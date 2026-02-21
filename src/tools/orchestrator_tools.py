from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from agents import FunctionTool, function_tool

from src.infra.firebase_client import get_storage_client, get_document_client
from src.infra.late_client import get_late_client


# Error collection path (root level)
ERRORS_COLLECTION = "errors"


@function_tool(
    name_override="upload_file",
    description_override="Upload a file to Firebase Storage from bytes data. Returns path and public_url.",
    strict_mode=False,
)
async def upload_file(
    file_data: bytes,
    destination_path: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Upload a file to Firebase Storage.

    Args:
        file_data: File content as bytes.
        destination_path: Target path in storage (e.g., "images/photo.jpg").
        content_type: MIME type (optional, auto-detected if not provided).

    Returns:
        dict with name, path, and public_url.
    """
    storage_client = get_storage_client()
    result = storage_client.upload_file(
        file_data=file_data,
        destination_path=destination_path,
        content_type=content_type,
    )
    return result


@function_tool(
    name_override="list_files",
    description_override="List files in Firebase Storage with optional prefix filter.",
)
async def list_files(
    prefix: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """
    List files in Firebase Storage.

    Args:
        prefix: Path prefix to filter files (like a folder).
        max_results: Maximum number of results to return.

    Returns:
        dict with items list containing file info.
    """
    storage_client = get_storage_client()
    items = storage_client.list_files(prefix=prefix, max_results=max_results)
    return {"items": items}


@function_tool(
    name_override="delete_file",
    description_override="Delete a file from Firebase Storage by path.",
)
async def delete_file(file_path: str) -> dict[str, Any]:
    """
    Delete a file from Firebase Storage.

    Args:
        file_path: Path of the file to delete.

    Returns:
        dict with success status.
    """
    storage_client = get_storage_client()
    try:
        storage_client.delete_file(file_path)
        return {"success": True, "message": f"File deleted: {file_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool(
    name_override="get_document",
    description_override=(
        "Get a document from Firestore. "
        "Use document_path for full path like 'businesses/abc/instagram_stats/week-2026-05'. "
        "Or use collection + document_id separately."
    ),
    strict_mode=False,
)
async def get_document(
    document_path: str | None = None,
    document_id: str | None = None,
    collection: str = "documents",
) -> dict[str, Any]:
    """
    Get a document from Firestore.

    Args:
        document_path: Full document path (e.g., 'businesses/abc/instagram_stats/week-2026-05').
                       If provided, collection and document_id are ignored.
        document_id: ID of the document to fetch (used with collection).
        collection: Collection name (default: "documents").

    Returns:
        dict with document data or error.
    """
    # Parse full path if provided
    if document_path:
        parts = document_path.split("/")
        if len(parts) < 2 or len(parts) % 2 != 0:
            return {"success": False, "error": f"Invalid document path: {document_path}. Must have even number of segments."}
        document_id = parts[-1]
        collection = "/".join(parts[:-1])

    if not document_id:
        return {"success": False, "error": "Either document_path or document_id must be provided"}

    doc_client = get_document_client(collection)
    doc = doc_client.get_document(document_id)
    if doc is None:
        return {"success": False, "error": "Document not found", "document_path": f"{collection}/{document_id}"}
    return {"success": True, "data": doc, "document_path": f"{collection}/{document_id}"}


@function_tool(
    name_override="save_document",
    description_override=(
        "Save or update a document in Firestore. "
        "Use document_path for full path like 'businesses/abc/instagram_stats/week-2026-05'. "
        "CRITICAL: Use merge=True to preserve existing data (e.g., metrics when adding summary)."
    ),
    strict_mode=False,
)
async def save_document(
    data: dict[str, Any],
    document_path: str | None = None,
    document_id: str | None = None,
    collection: str = "documents",
    merge: bool = True,
) -> dict[str, Any]:
    """
    Save or update a document in Firestore.

    Args:
        data: Document data to save.
        document_path: Full document path (e.g., 'businesses/abc/instagram_stats/week-2026-05').
                       If provided, collection and document_id are ignored.
        document_id: ID of the document (used with collection).
        collection: Collection name (default: "documents").
        merge: If True, merge with existing data; if False, overwrite completely.

    Returns:
        dict with document_path.
    """
    # Parse full path if provided
    if document_path:
        parts = document_path.split("/")
        if len(parts) < 2 or len(parts) % 2 != 0:
            return {"success": False, "error": f"Invalid document path: {document_path}. Must have even number of segments."}
        document_id = parts[-1]
        collection = "/".join(parts[:-1])

    if not document_id:
        return {"success": False, "error": "Either document_path or document_id must be provided"}

    doc_client = get_document_client(collection)
    result = doc_client.set_document(document_id, data, merge=merge)
    return {"success": True, "document_path": f"{collection}/{document_id}", **result}


@function_tool(
    name_override="query_documents",
    description_override="Query documents in Firestore collection.",
    strict_mode=False,
)
async def query_documents(
    field: str,
    operator: str,
    value: Any,
    collection: str = "documents",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Query documents in Firestore.

    Args:
        field: Field to query.
        operator: Comparison operator ("==", ">", "<", ">=", "<=", "in", "array-contains").
        value: Value to compare against.
        collection: Collection name (default: "documents").
        limit: Maximum results.

    Returns:
        dict with results list.
    """
    doc_client = get_document_client(collection)
    results = doc_client.query_documents(field, operator, value, limit)
    return {"success": True, "results": results, "count": len(results)}


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
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "file_url": file_url,
                "content_type": content_type,
                "is_story": is_story,
            }

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
        return {
            "success": False,
            "error": f"Instagram posting failed: {type(exc).__name__}: {exc}",
            "file_url": file_url,
            "content_type": content_type,
            "is_story": is_story,
        }


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

                     Example: [
                         {"url": "https://...", "type": "image", "aspect_ratio": "1:1"},
                         {"url": "https://...", "type": "video", "aspect_ratio": "1:1"}
                     ]

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

        # Validate aspect ratio consistency
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
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "item_count": len(media_items),
            }

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
        return {
            "success": False,
            "error": f"Instagram carousel posting failed: {type(exc).__name__}: {exc}",
            "item_count": len(media_items),
        }


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
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "item_count": len(media_items),
            }

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
        return {
            "success": False,
            "error": f"TikTok carousel posting failed: {type(exc).__name__}: {exc}",
            "item_count": len(media_items),
        }


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
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
            }

        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "video",
            "message": "Successfully posted video to TikTok",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"TikTok video posting failed: {type(exc).__name__}: {exc}",
        }


@function_tool(
    name_override="post_on_linkedin",
    description_override=(
        "Post to LinkedIn via Late API (text-only, single image, or video).\n\n"
        "Automatically fetches linkedin_account_id from the business profile in Firebase.\n\n"
        "SCENARIOS:\n"
        "1. Text-only: Provide only content (no media_url)\n"
        "2. Image post: Provide content + media_url + media_type='image'\n"
        "3. Video post: Provide content + media_url + media_type='video'\n\n"
        "REQUIRED:\n"
        "- business_id: Business ID to fetch linkedin_account_id from Firebase\n"
        "- content: Post text (max 3000 chars). Optional only if media_url provided.\n\n"
        "OPTIONAL:\n"
        "- media_url: Public URL of image or video\n"
        "- media_type: 'image' or 'video' (required if media_url provided)\n"
        "- first_comment: Auto-posted first comment (recommended for links - LinkedIn suppresses posts with URLs by 40-50%%)\n"
        "- disable_link_preview: Suppress URL preview card (default: false)\n"
        "- organization_urn: Post as company page (format: urn:li:organization:XXXXX)\n"
        "- scheduled_for: ISO datetime for scheduled post"
    ),
    strict_mode=False,
)
async def post_on_linkedin(
    business_id: str,
    content: str | None = None,
    media_url: str | None = None,
    media_type: Literal["image", "video"] | None = None,
    first_comment: str | None = None,
    disable_link_preview: bool | None = None,
    organization_urn: str | None = None,
    scheduled_for: str | None = None,
) -> dict[str, Any]:
    """
    Post to LinkedIn via Late API.

    Args:
        business_id: Business ID to fetch linkedin_account_id from Firebase.
        content: Post text (max 3000 chars).
        media_url: Public URL of image or video (optional).
        media_type: "image" or "video" (required if media_url provided).
        first_comment: Auto-posted first comment (optional).
        disable_link_preview: Suppress URL preview card (optional).
        organization_urn: Post as company page (optional).
        scheduled_for: ISO datetime for scheduled post (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if not content and not media_url:
            return {
                "success": False,
                "error": "Either content or media_url must be provided",
            }

        if content and len(content) > 3000:
            return {
                "success": False,
                "error": f"Content exceeds 3000 characters ({len(content)} chars)",
            }

        if media_url and not media_type:
            return {
                "success": False,
                "error": "media_type is required when media_url is provided. Use 'image' or 'video'.",
            }

        if media_url and not media_url.startswith("http"):
            return {
                "success": False,
                "error": f"Invalid media URL '{media_url}'. URL must start with http:// or https://",
            }

        # --- Fetch linkedin_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        linkedin_account_id = business.get("linkedin_account_id")
        if not linkedin_account_id:
            return {
                "success": False,
                "error": f"No linkedin_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(linkedin_account_id)
        result = await late.post_linkedin(
            content=content,
            media_url=media_url,
            media_type=media_type,
            first_comment=first_comment,
            disable_link_preview=disable_link_preview,
            organization_urn=organization_urn,
            scheduled_for=scheduled_for,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
            }

        content_type = media_type or "text"
        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": content_type,
            "message": f"Successfully posted {content_type} to LinkedIn",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"LinkedIn posting failed: {type(exc).__name__}: {exc}",
        }


@function_tool(
    name_override="post_carousel_on_linkedin",
    description_override=(
        "Post a multi-image carousel (2-20 images) to LinkedIn via Late API.\n\n"
        "Automatically fetches linkedin_account_id from the business profile in Firebase.\n\n"
        "REQUIRED:\n"
        "- media_items: List of 2-20 image objects. Each must have 'url' and 'type': 'image'\n"
        "- business_id: Business ID to fetch linkedin_account_id from Firebase\n\n"
        "OPTIONAL:\n"
        "- content: Post text (max 3000 chars)\n"
        "- first_comment: Auto-posted first comment\n"
        "- disable_link_preview: Suppress URL preview card\n"
        "- organization_urn: Post as company page (format: urn:li:organization:XXXXX)\n"
        "- scheduled_for: ISO datetime for scheduled post\n\n"
        "NOTE: Cannot mix media types. All items must be images."
    ),
    strict_mode=False,
)
async def post_carousel_on_linkedin(
    media_items: list[dict],
    business_id: str,
    content: str | None = None,
    first_comment: str | None = None,
    disable_link_preview: bool | None = None,
    organization_urn: str | None = None,
    scheduled_for: str | None = None,
) -> dict[str, Any]:
    """
    Post a multi-image carousel to LinkedIn via Late API.

    Args:
        media_items: List of image items (2-20).
        business_id: Business ID to fetch linkedin_account_id from Firebase.
        content: Post text (max 3000 chars, optional).
        first_comment: Auto-posted first comment (optional).
        disable_link_preview: Suppress URL preview card (optional).
        organization_urn: Post as company page (optional).
        scheduled_for: ISO datetime for scheduled post (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if len(media_items) < 2:
            return {
                "success": False,
                "error": "LinkedIn carousel requires at least 2 media items",
            }

        if len(media_items) > 20:
            return {
                "success": False,
                "error": "LinkedIn carousel cannot have more than 20 media items",
            }

        if content and len(content) > 3000:
            return {
                "success": False,
                "error": f"Content exceeds 3000 characters ({len(content)} chars)",
            }

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

        # --- Fetch linkedin_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        linkedin_account_id = business.get("linkedin_account_id")
        if not linkedin_account_id:
            return {
                "success": False,
                "error": f"No linkedin_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(linkedin_account_id)
        result = await late.post_linkedin_carousel(
            media_items=media_items,
            content=content,
            first_comment=first_comment,
            disable_link_preview=disable_link_preview,
            organization_urn=organization_urn,
            scheduled_for=scheduled_for,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "item_count": len(media_items),
            }

        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "carousel",
            "item_count": result.get("item_count"),
            "message": f"Successfully posted carousel with {result.get('item_count')} images to LinkedIn",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"LinkedIn carousel posting failed: {type(exc).__name__}: {exc}",
            "item_count": len(media_items),
        }


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
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "video_url": video_url,
            }

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
        return {
            "success": False,
            "error": f"YouTube posting failed: {type(exc).__name__}: {exc}",
            "video_url": video_url,
        }


def get_orchestrator_tools() -> list[FunctionTool]:
    """Return the list of tools for the orchestrator agent."""
    return [
        upload_file,
        list_files,
        delete_file,
        get_document,
        save_document,
        query_documents,
        post_on_instagram,
        post_carousel_on_instagram,
        post_on_youtube,
        post_carousel_on_tiktok,
        post_on_tiktok,
        post_on_linkedin,
        post_carousel_on_linkedin,
        report_error,
    ]


@function_tool(
    name_override="report_error",
    description_override=(
        "Report an error to Firebase for admin review. "
        "Use this when you encounter an error that needs human attention. "
        "Provide clear details about what you were trying to do and what went wrong."
    ),
    strict_mode=False,
)
async def report_error(
    business_id: str,
    agent: str,
    task: str,
    error_message: str,
    error_type: Literal["api_error", "validation_error", "timeout", "rate_limit", "not_found", "permission", "unknown"] = "unknown",
    severity: Literal["low", "medium", "high", "critical"] = "medium",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Report an error to Firebase for admin/panel review.

    Args:
        business_id: Business ID where error occurred.
        agent: Which agent reported the error (e.g., "image_agent", "marketing_agent").
        task: What the agent was trying to do.
        error_message: The error message or description.
        error_type: Type of error (api_error, validation_error, timeout, rate_limit, not_found, permission, unknown).
        severity: Error severity (low, medium, high, critical).
        context: Additional context data (optional).

    Returns:
        dict with success status and error_id.
    """
    try:
        doc_client = get_document_client(ERRORS_COLLECTION)

        error_data = {
            "business_id": business_id,
            "agent": agent,
            "task": task,
            "error_message": error_message,
            "error_type": error_type,
            "severity": severity,
            "context": context,
            "created_at": datetime.now().isoformat(),
            "resolved": False,
            "resolved_at": None,
            "resolution_note": None,
        }

        result = doc_client.add_document(error_data)
        error_id = result.get("documentId")

        return {
            "success": True,
            "error_id": error_id,
            "message": "Error reported successfully. Admin will review.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to report error: {e}"}


@function_tool(
    name_override="fetch_business",
    description_override=(
        "Fetches a business profile from Firestore by business_id. "
        "Returns business info including name, colors, logo URL, website URL, profile data, "
        "instagram_id for Instagram posting, late_profile_id for Instagram analytics, "
        "youtube_id for YouTube posting, tiktok_account_id for TikTok posting, "
        "and linkedin_account_id for LinkedIn posting via Late API."
    ),
)
async def fetch_business(business_id: str) -> dict[str, Any]:
    """
    Fetch business profile from Firestore.

    Args:
        business_id: Firestore document ID in 'businesses' collection.

    Returns:
        dict: Business data including name, colors, logo, website, profile, instagram_id,
              late_profile_id (for analytics), youtube_id, tiktok_account_id, and linkedin_account_id.
    """
    doc_client = get_document_client("businesses")
    doc = doc_client.get_document(business_id)
    if doc is None:
        return {"success": False, "business_id": business_id, "error": "Business not found"}

    return {
        "success": True,
        "business_id": business_id,
        "name": doc.get("name"),
        "colors": doc.get("colors"),
        "logo": doc.get("logo"),  # Cloud Storage URL
        "website": doc.get("website"),  # Business website URL for SEO analysis
        "profile": doc.get("profile"),  # Dynamic map
        "instagram_id": doc.get("instagram_id"),  # Late API account ID (acc_xxxxx) - for POSTING
        "late_profile_id": doc.get("late_profile_id"),  # Late profile ID (raw ObjectId) - for ANALYTICS
        "youtube_id": doc.get("youtube_id"),  # Late API YouTube account ID (acc_xxxxx)
        "tiktok_account_id": doc.get("tiktok_account_id"),  # Late API TikTok account ID
        "linkedin_account_id": doc.get("linkedin_account_id"),  # Late API LinkedIn account ID
    }


__all__ = [
    "upload_file",
    "list_files",
    "delete_file",
    "get_document",
    "save_document",
    "query_documents",
    "post_on_instagram",
    "post_carousel_on_instagram",
    "post_on_youtube",
    "post_carousel_on_tiktok",
    "post_on_tiktok",
    "post_on_linkedin",
    "post_carousel_on_linkedin",
    "report_error",
    "get_orchestrator_tools",
    "fetch_business",
]
