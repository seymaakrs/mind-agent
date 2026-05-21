"""Sales Director memory tools — Firestore-backed persistent notes.

Path: businesses/{business_id}/sales_memory/notes (single doc, merge=True).

Pattern mirror: src/tools/sales/reporting_tools.py (_x_impl async + function_tool).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


log = logging.getLogger(__name__)

_MEMORY_DOC_ID = "notes"


def _resolve_business_id(business_id: str | None) -> str | None:
    if business_id and business_id.strip():
        return business_id.strip()
    env = os.environ.get("SALES_DIRECTOR_BUSINESS_ID") or ""
    return env.strip() or None


def _collection(business_id: str) -> str:
    return f"businesses/{business_id}/sales_memory"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_sales_memory_impl(business_id: str | None = None) -> dict[str, Any]:
    bid = _resolve_business_id(business_id)
    if not bid:
        return {
            "success": False,
            "error": "business_id missing (set SALES_DIRECTOR_BUSINESS_ID or pass arg).",
            "error_code": "INVALID_INPUT",
            "retryable": False,
            "user_message_tr": "Hafiza icin business_id gerekli.",
        }
    try:
        doc_client = get_document_client(_collection(bid))
        data = doc_client.get_document(_MEMORY_DOC_ID)
        if not data:
            return {
                "success": True,
                "business_id": bid,
                "exists": False,
                "notes": "",
                "summary_tr": "Henuz kayitli satis hafizasi yok.",
            }
        data.pop("documentId", None)
        return {
            "success": True,
            "business_id": bid,
            "exists": True,
            "notes": data.get("notes", ""),
            "updated_at": data.get("updated_at"),
            "summary_tr": f"Satis hafizasi yuklendi ({len(data.get('notes', ''))} karakter).",
        }
    except Exception as exc:
        log.warning("get_sales_memory failed business=%s: %s", bid, exc)
        return {
            "success": False,
            "error": str(exc),
            "error_code": "UNKNOWN",
            "service": "firestore",
            "retryable": True,
            "user_message_tr": "Hafiza okunamadi.",
        }


async def _update_sales_memory_impl(
    notes: str,
    business_id: str | None = None,
) -> dict[str, Any]:
    bid = _resolve_business_id(business_id)
    if not bid:
        return {
            "success": False,
            "error": "business_id missing.",
            "error_code": "INVALID_INPUT",
            "retryable": False,
            "user_message_tr": "Hafiza icin business_id gerekli.",
        }
    if notes is None:
        notes = ""
    try:
        doc_client = get_document_client(_collection(bid))
        updated_at = _now_iso()
        doc_client.set_document(
            _MEMORY_DOC_ID,
            {"notes": notes, "updated_at": updated_at},
            merge=True,
        )
        return {
            "success": True,
            "business_id": bid,
            "updated_at": updated_at,
            "chars": len(notes),
            "summary_tr": f"Satis hafizasi guncellendi ({len(notes)} karakter).",
        }
    except Exception as exc:
        log.error("update_sales_memory failed business=%s: %s", bid, exc)
        return {
            "success": False,
            "error": str(exc),
            "error_code": "UNKNOWN",
            "service": "firestore",
            "retryable": True,
            "user_message_tr": "Hafiza kaydedilemedi.",
        }


get_sales_memory = function_tool(
    name_override="get_sales_memory",
    description_override=(
        "Satis Direktoru'nun kalici hafizasi (Firestore). "
        "businesses/{business_id}/sales_memory/notes yolundan notlari okur. "
        "business_id opsiyonel — verilmezse SALES_DIRECTOR_BUSINESS_ID env'i kullanilir. "
        "Returns {success, notes, updated_at, exists, summary_tr}."
    ),
    strict_mode=False,
)(_get_sales_memory_impl)


update_sales_memory = function_tool(
    name_override="update_sales_memory",
    description_override=(
        "Satis Direktoru hafizasini Firestore'a yazar (overwrite notes field). "
        "REQUIRED: notes (yeni tam metin). business_id opsiyonel — verilmezse "
        "SALES_DIRECTOR_BUSINESS_ID env'i. updated_at otomatik ISO UTC now. "
        "Returns {success, business_id, updated_at, chars, summary_tr}."
    ),
    strict_mode=False,
)(_update_sales_memory_impl)


def get_memory_tools() -> list:
    return [get_sales_memory, update_sales_memory]


__all__ = [
    "get_sales_memory",
    "update_sales_memory",
    "get_memory_tools",
    "_get_sales_memory_impl",
    "_update_sales_memory_impl",
]
