"""
Firestore generic okuma/yazma tool'lari (LLM-callable).

SECURITY (SECURITY_REPORT_TR.md Madde 2 — Firestore IDOR):
- business_id ZORUNLU.
- Path mutlaka 'businesses/{business_id}/...' ile baslamali.
- Subcollection adi ALLOWED_BUSINESS_SUBCOLLECTIONS whitelist'inde olmali.
- Tum path bilesenleri safe_path_segment ile dogrulanir (traversal koruma).

Top-level koleksiyonlar (settings, users, errors, ...) bu tool'lar uzerinden
ERISILEMEZ. Bu koleksiyonlara ihtiyac duyan dedicated tool'lar (orneğin
report_error → errors) kendi izolasyon mantiklarina sahiptir.
"""
from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client
from src.infra.path_safety import safe_path_segment


# Sozlesmedeki sub-collection whitelist'i (CLAUDE.md "Firestore Yapisi" + analiz).
# businesses/{business_id} altinda izin verilen sub-collection'lar:
ALLOWED_BUSINESS_SUBCOLLECTIONS: frozenset[str] = frozenset(
    {
        "instagram_stats",
        "reports",
        "seo",
        "agent_memory",
        "media",
        "instagram_posts",
        "youtube_videos",
        "content_calendar",
        "tasks",
        "logs",
        "dry_run_logs",
        "tiktok_posts",
        "linkedin_posts",
        "media_tracking",
        "marketing_memory",
    }
)


def _service_error(error_code: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "service": "firestore",
        "error": error,
        "error_code": error_code,
        "retryable": False,
        "user_message_tr": (
            "Bu Firestore yolu yetkiniz disinda veya gecerli bir formatta degil."
        ),
    }


def _validate_firestore_path(
    *,
    business_id: str,
    document_path: str | None,
    document_id: str | None,
    collection: str | None,
) -> dict[str, Any] | None:
    """
    business_id + path/collection+id kombinasyonunu IDOR'a karsi dogrular.

    Returns:
        None: gecerli, caller normal akista devam edebilir.
        dict: ServiceError pattern'inde (error_code, ...).
    """
    # 1. business_id format kontrolu
    if not business_id or not isinstance(business_id, str):
        return _service_error("INVALID_INPUT", "business_id is required.")
    try:
        safe_path_segment(business_id)
    except ValueError as exc:
        return _service_error("INVALID_INPUT", f"business_id invalid: {exc}")

    # 2. Path veya collection+id formundan effective segment'leri cikar
    if document_path:
        # path verilirse oncelikli; collection ve document_id ignore.
        parts = [p for p in document_path.split("/") if p != ""]
        # Tum bos segment varsa: original split bos string birakir; biz filtre
        # ettik. Ama bos segment bir traversal (cift slash) sinyali — reddet.
        if document_path.count("//") > 0:
            return _service_error(
                "INVALID_INPUT",
                f"Document path contains empty segment: {document_path!r}",
            )
        if len(parts) < 2 or len(parts) % 2 != 0:
            return _service_error(
                "INVALID_INPUT",
                (
                    f"Invalid document path: {document_path!r}. "
                    "Must have even number of non-empty segments (collection/doc/coll/doc...)."
                ),
            )
        coll_segments = parts[:-1]
        effective_doc_id = parts[-1]
    else:
        if not collection or not isinstance(collection, str):
            return _service_error(
                "INVALID_INPUT",
                "Either document_path or (collection + document_id) is required.",
            )
        if not document_id or not isinstance(document_id, str):
            return _service_error("INVALID_INPUT", "document_id is required.")
        coll_segments = [p for p in collection.split("/") if p != ""]
        effective_doc_id = document_id

    # 3. Tum segment'ler safe_path_segment'ten gecmeli (traversal/separator/null)
    for seg in coll_segments + [effective_doc_id]:
        try:
            safe_path_segment(seg)
        except ValueError as exc:
            return _service_error("INVALID_INPUT", f"path segment {seg!r}: {exc}")

    # 4. Path mutlaka 'businesses/{business_id}' ile baslamali
    if len(coll_segments) < 2:
        return _service_error(
            "PERMISSION_DENIED",
            "Path must start with 'businesses/{business_id}/...'",
        )
    if coll_segments[0] != "businesses":
        return _service_error(
            "PERMISSION_DENIED",
            (
                f"Top-level collection {coll_segments[0]!r} not allowed. "
                "Only 'businesses/{business_id}/<allowed_subcollection>' paths."
            ),
        )
    if coll_segments[1] != business_id:
        return _service_error(
            "PERMISSION_DENIED",
            (
                f"Path business_id {coll_segments[1]!r} does not match "
                f"caller business_id {business_id!r}."
            ),
        )

    # 5. Sub-collection (varsa) whitelist'te olmali. coll_segments minimum 2
    # ('businesses', business_id). Eger subcollection varsa coll_segments[2]
    # ondan sonraki nested olabilir; biz sadece ilk subcollection katmanini
    # whitelist'te tutuyoruz (nested'lar zaten parent'in altinda).
    if len(coll_segments) >= 3:
        sub = coll_segments[2]
        if sub not in ALLOWED_BUSINESS_SUBCOLLECTIONS:
            return _service_error(
                "PERMISSION_DENIED",
                (
                    f"Subcollection {sub!r} not in whitelist. Allowed: "
                    f"{sorted(ALLOWED_BUSINESS_SUBCOLLECTIONS)}"
                ),
            )

    return None


@function_tool(
    name_override="get_document",
    description_override=(
        "Get a document from Firestore under businesses/{business_id}/<allowed>. "
        "REQUIRED: business_id. Either provide full document_path "
        "('businesses/{business_id}/reports/r1') or (collection + document_id)."
    ),
    strict_mode=False,
)
async def get_document(
    business_id: str,
    document_path: str | None = None,
    document_id: str | None = None,
    collection: str | None = None,
) -> dict[str, Any]:
    """
    Get a document from Firestore.

    Args:
        business_id: REQUIRED. Caller's business ID; path must match.
        document_path: Full path ('businesses/{business_id}/reports/r1').
        document_id: Used with `collection` if document_path not provided.
        collection: Used with `document_id`.

    Returns:
        dict with document data or ServiceError dict.
    """
    err = _validate_firestore_path(
        business_id=business_id,
        document_path=document_path,
        document_id=document_id,
        collection=collection,
    )
    if err is not None:
        return err

    # Validation passed — derive effective values
    if document_path:
        parts = [p for p in document_path.split("/") if p != ""]
        eff_doc_id = parts[-1]
        eff_collection = "/".join(parts[:-1])
    else:
        eff_doc_id = document_id  # type: ignore[assignment]
        eff_collection = collection  # type: ignore[assignment]

    doc_client = get_document_client(eff_collection)
    doc = doc_client.get_document(eff_doc_id)
    if doc is None:
        return {
            "success": False,
            "error": "Document not found",
            "error_code": "NOT_FOUND",
            "document_path": f"{eff_collection}/{eff_doc_id}",
        }
    return {
        "success": True,
        "data": doc,
        "document_path": f"{eff_collection}/{eff_doc_id}",
    }


@function_tool(
    name_override="save_document",
    description_override=(
        "Save or update a document in Firestore under businesses/{business_id}/<allowed>. "
        "REQUIRED: business_id. Use merge=True to preserve existing data."
    ),
    strict_mode=False,
)
async def save_document(
    business_id: str,
    data: dict[str, Any],
    document_path: str | None = None,
    document_id: str | None = None,
    collection: str | None = None,
    merge: bool = True,
) -> dict[str, Any]:
    """
    Save or update a document in Firestore.

    Args:
        business_id: REQUIRED. Caller's business ID; path must match.
        data: Document data to save.
        document_path: Full path ('businesses/{business_id}/reports/r1').
        document_id: Used with `collection`.
        collection: Used with `document_id`.
        merge: If True, merge with existing data; if False, overwrite.

    Returns:
        dict with document_path and result, or ServiceError dict.
    """
    err = _validate_firestore_path(
        business_id=business_id,
        document_path=document_path,
        document_id=document_id,
        collection=collection,
    )
    if err is not None:
        return err

    if document_path:
        parts = [p for p in document_path.split("/") if p != ""]
        eff_doc_id = parts[-1]
        eff_collection = "/".join(parts[:-1])
    else:
        eff_doc_id = document_id  # type: ignore[assignment]
        eff_collection = collection  # type: ignore[assignment]

    doc_client = get_document_client(eff_collection)
    result = doc_client.set_document(eff_doc_id, data, merge=merge)
    return {
        "success": True,
        "document_path": f"{eff_collection}/{eff_doc_id}",
        **result,
    }


@function_tool(
    name_override="query_documents",
    description_override=(
        "Query documents in a Firestore collection under businesses/{business_id}/<allowed>. "
        "REQUIRED: business_id and collection (must be a path under the caller's business)."
    ),
    strict_mode=False,
)
async def query_documents(
    business_id: str,
    collection: str,
    field: str,
    operator: str,
    value: Any,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Query documents in a Firestore collection.

    Args:
        business_id: REQUIRED. Caller's business ID; collection must be under it.
        collection: Collection path (e.g., 'businesses/{bid}/reports').
        field: Field to query.
        operator: Comparison operator ("==", ">", "<", ">=", "<=", "in", "array-contains").
        value: Value to compare against.
        limit: Maximum results.

    Returns:
        dict with results list or ServiceError.
    """
    # query_documents calismasi icin: collection path'i 'businesses/{bid}/<sub>'
    # olmali. Doc-id yok (query). Validator'i hayalî bir document_id ile
    # cagiriyoruz; sadece collection path'i kontrol etmek icin.
    err = _validate_firestore_path(
        business_id=business_id,
        document_path=None,
        document_id="__query_placeholder__",
        collection=collection,
    )
    if err is not None:
        return err

    doc_client = get_document_client(collection)
    results = doc_client.query_documents(field, operator, value, limit)
    return {"success": True, "results": results, "count": len(results)}


__all__ = [
    "get_document",
    "save_document",
    "query_documents",
    "ALLOWED_BUSINESS_SUBCOLLECTIONS",
    "_validate_firestore_path",
]
