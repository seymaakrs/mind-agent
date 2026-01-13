from __future__ import annotations

from typing import Any, Literal

from agents import FunctionTool, function_tool

from src.infra.firebase_client import get_storage_client, get_document_client
from src.infra.cloudconvert_client import get_cloudconvert_client
from src.infra.instagram_client import InstagramClient


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
        "Post content to Instagram. Automatically converts media format for Instagram compatibility. "
        "Requires instagram_account_id and instagram_access_token from business profile. "
        "\n\n"
        "IMPORTANT: You MUST provide instagram_account_id and instagram_access_token from the business profile. "
        "These are found in the fetch_business result under 'instagram_account_id' and 'instagram_access_token' fields."
    ),
    strict_mode=False,
)
async def post_on_instagram(
    file_url: str,
    caption: str,
    content_type: Literal["image", "video"],
    instagram_account_id: str,
    instagram_access_token: str,
) -> dict[str, Any]:
    """
    Post content to Instagram.

    Automatically converts:
    - Images: PNG/WebP → JPG (via CloudConvert)
    - Videos: Any → MP4 with x264/aac codec (via CloudConvert)

    Args:
        file_url: Firebase Storage public URL of the file to post.
        caption: Post caption.
        content_type: Type of content ("image" or "video").
        instagram_account_id: Instagram Business Account ID from business profile.
        instagram_access_token: Instagram Graph API access token from business profile.

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # Step 1: Convert media format via CloudConvert
        cloudconvert = get_cloudconvert_client()

        if content_type == "image":
            converted_url = await cloudconvert.convert_image_to_jpg(file_url)
        else:  # video
            converted_url = await cloudconvert.convert_video_for_instagram(file_url)

        # Step 2: Post to Instagram
        instagram = InstagramClient(
            account_id=instagram_account_id,
            access_token=instagram_access_token,
        )

        if content_type == "image":
            result = await instagram.post_image(converted_url, caption)
        else:  # video
            result = await instagram.post_video_reel(converted_url, caption)

        return {
            "success": True,
            "post_id": result.get("post_id"),
            "creation_id": result.get("creation_id"),
            "content_type": content_type,
            "message": f"Successfully posted {content_type} to Instagram",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Instagram posting failed: {type(exc).__name__}: {exc}",
            "file_url": file_url,
            "content_type": content_type,
        }


@function_tool(
    name_override="post_carousel_on_instagram",
    description_override=(
        "Post a carousel (multiple images/videos) to Instagram. "
        "Automatically converts media formats for Instagram compatibility.\n\n"
        "REQUIRED PARAMETERS:\n"
        "1. media_items: List of 2-10 media objects. EACH object MUST have:\n"
        '   - "url": Full Firebase Storage URL (e.g., "https://storage.googleapis.com/...")\n'
        '   - "type": Either "image" or "video"\n'
        '   Example: [{"url": "https://storage.googleapis.com/bucket/img1.png", "type": "image"}, '
        '{"url": "https://storage.googleapis.com/bucket/img2.png", "type": "image"}]\n'
        "2. caption: Post caption text\n"
        "3. instagram_account_id: From business profile\n"
        "4. instagram_access_token: From business profile\n\n"
        "DO NOT include business_id - it is NOT a parameter of this tool."
    ),
    strict_mode=False,
)
async def post_carousel_on_instagram(
    media_items: list[dict],
    caption: str,
    instagram_account_id: str,
    instagram_access_token: str,
) -> dict[str, Any]:
    """
    Post a carousel to Instagram.

    Automatically converts:
    - Images: PNG/WebP → JPG (via CloudConvert)
    - Videos: Any → MP4 with x264/aac codec (via CloudConvert)

    Args:
        media_items: List of media items. Each item: {"url": str, "type": "image" | "video"}
                     Example: [{"url": "https://...", "type": "image"}, {"url": "https://...", "type": "video"}]
        caption: Post caption.
        instagram_account_id: Instagram Business Account ID from business profile.
        instagram_access_token: Instagram Graph API access token from business profile.

    Returns:
        dict with success, post_id, and details.
    """
    try:
        if len(media_items) < 2:
            return {"success": False, "error": "Carousel requires at least 2 media items"}

        if len(media_items) > 10:
            return {"success": False, "error": "Carousel cannot have more than 10 media items"}

        # Validate media_items structure and URL accessibility
        import httpx
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

        # Pre-check URL accessibility before CloudConvert
        async with httpx.AsyncClient(timeout=10.0) as client:
            for i, item in enumerate(media_items):
                url = item.get("url")
                try:
                    resp = await client.head(url)
                    if resp.status_code == 403:
                        return {"success": False, "error": f"media_items[{i}] URL returns 403 Forbidden. File may not be public. URL: {url[:100]}..."}
                    if resp.status_code == 404:
                        return {"success": False, "error": f"media_items[{i}] URL returns 404 Not Found. File does not exist. URL: {url[:100]}..."}
                    if resp.status_code >= 400:
                        return {"success": False, "error": f"media_items[{i}] URL returns {resp.status_code}. URL: {url[:100]}..."}
                except Exception as e:
                    return {"success": False, "error": f"media_items[{i}] URL is not accessible: {type(e).__name__}. URL: {url[:100]}..."}

        # Step 1: Convert all media formats via CloudConvert
        cloudconvert = get_cloudconvert_client()
        converted_items = []

        for item in media_items:
            url = item.get("url")
            media_type = item.get("type", "image")

            if media_type == "image":
                converted_url = await cloudconvert.convert_image_to_jpg(url)
            else:  # video
                converted_url = await cloudconvert.convert_video_for_instagram(url)

            converted_items.append({
                "url": converted_url,
                "type": media_type,
            })

        # Step 2: Post carousel to Instagram
        instagram = InstagramClient(
            account_id=instagram_account_id,
            access_token=instagram_access_token,
        )

        result = await instagram.post_carousel(converted_items, caption)

        return {
            "success": True,
            "post_id": result.get("post_id"),
            "creation_id": result.get("creation_id"),
            "content_type": "carousel",
            "item_count": result.get("item_count"),
            "message": f"Successfully posted carousel with {result.get('item_count')} items to Instagram",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Instagram carousel posting failed: {type(exc).__name__}: {exc}",
            "item_count": len(media_items),
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
    ]


__all__ = [
    "upload_file",
    "list_files",
    "delete_file",
    "get_document",
    "save_document",
    "query_documents",
    "post_on_instagram",
    "post_carousel_on_instagram",
    "get_orchestrator_tools",
]
