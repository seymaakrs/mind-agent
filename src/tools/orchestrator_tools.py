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
    description_override="Get a document from Firestore by ID. Returns document data.",
)
async def get_document(
    document_id: str,
    collection: str = "documents",
) -> dict[str, Any]:
    """
    Get a document from Firestore.

    Args:
        document_id: ID of the document to fetch.
        collection: Collection name (default: "documents").

    Returns:
        dict with document data or error.
    """
    doc_client = get_document_client(collection)
    doc = doc_client.get_document(document_id)
    if doc is None:
        return {"success": False, "error": "Document not found", "documentId": document_id}
    return {"success": True, "data": doc}


@function_tool(
    name_override="save_document",
    description_override="Save or update a document in Firestore.",
    strict_mode=False,
)
async def save_document(
    document_id: str,
    data: dict[str, Any],
    collection: str = "documents",
    merge: bool = True,
) -> dict[str, Any]:
    """
    Save or update a document in Firestore.

    Args:
        document_id: ID of the document.
        data: Document data to save.
        collection: Collection name (default: "documents").
        merge: If True, merge with existing data; if False, overwrite.

    Returns:
        dict with documentId.
    """
    doc_client = get_document_client(collection)
    result = doc_client.set_document(document_id, data, merge=merge)
    return {"success": True, **result}


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
        "instagram_id for Instagram posting, and youtube_id for YouTube posting via Late API."
    ),
)
async def fetch_business(business_id: str) -> dict[str, Any]:
    """
    Fetch business profile from Firestore.

    Args:
        business_id: Firestore document ID in 'businesses' collection.

    Returns:
        dict: Business data including name, colors, logo, website, profile, instagram_id, and youtube_id.
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
        "instagram_id": doc.get("instagram_id"),  # Late API account ID (acc_xxxxx)
        "youtube_id": doc.get("youtube_id"),  # Late API YouTube account ID (acc_xxxxx)
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
    "report_error",
    "get_orchestrator_tools",
    "fetch_business",
]
