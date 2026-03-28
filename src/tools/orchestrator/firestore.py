from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


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
