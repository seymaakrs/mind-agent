from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_storage_client


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
