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
    ]


__all__ = [
    "upload_file",
    "list_files",
    "delete_file",
    "get_document",
    "save_document",
    "query_documents",
    "post_on_instagram",
    "get_orchestrator_tools",
]
