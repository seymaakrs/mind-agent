"""Sales Manager structured memory tools.

Satış Müdürü'nün kararlarını, tercihlerini, öğrendiklerini ve önemli
kontaklarını yapılandırılmış (kategorize) şekilde Firestore'da saklar.

Firestore path: ``businesses/{business_id}/sales_memory/{category}/notes/{key}``

Kategoriler (sabit):
  - decisions   : Müdürün verdiği kararlar (örn. "Slowdays pause edildi")
  - preferences : Tercih edilen yaklaşımlar (örn. "Cumartesi sabah mesaj atma")
  - learnings   : Çıkarılan dersler (örn. "Boutique oteller fiyat sormaz")
  - contacts    : Önemli kişiler (örn. "Marmaris bölge müdürü: ...")

Her aksiyon için `reason` zorunludur (audit log + LLM bağlam doğruluğu).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


log = logging.getLogger(__name__)


VALID_CATEGORIES: set[str] = {"decisions", "preferences", "learnings", "contacts"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notes_path(business_id: str, category: str) -> str:
    """Collection path that holds notes for a given category."""
    return f"businesses/{business_id}/sales_memory/{category}/notes"


def _validate_category(category: str) -> str | None:
    """Return error message if invalid, else None."""
    if not category or category not in VALID_CATEGORIES:
        return (
            f"Geçersiz category '{category}'. Geçerli: "
            f"{sorted(VALID_CATEGORIES)}"
        )
    return None


# ---------------------------------------------------------------------------
# 1) save_sales_memory
# ---------------------------------------------------------------------------


async def _save_sales_memory_impl(
    business_id: str,
    category: str,
    key: str,
    value: str,
    reason: str,
) -> dict[str, Any]:
    """Yeni bir hafıza notu yaz (merge=True)."""
    if not business_id or not business_id.strip():
        return {"success": False, "error": "business_id zorunlu."}
    err = _validate_category(category)
    if err:
        return {"success": False, "error": err}
    if not key or len(key.strip()) < 2:
        return {"success": False, "error": "key en az 2 karakter olmalı."}
    if not value or len(value.strip()) < 5:
        return {"success": False, "error": "value en az 5 karakter olmalı."}
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "reason en az 5 karakter olmalı."}

    business_id = business_id.strip()
    key = key.strip()
    try:
        doc_client = get_document_client(_notes_path(business_id, category))
        existing = doc_client.get_document(key)
        now = _now_iso()
        data: dict[str, Any] = {
            "value": value,
            "category": category,
            "key": key,
            "reason": reason,
            "updated_at": now,
        }
        if not existing:
            data["created_at"] = now
        doc_client.set_document(key, data, merge=True)
        log.info(
            "save_sales_memory: business=%s category=%s key=%s reason=%s",
            business_id, category, key, reason,
        )
        return {
            "success": True,
            "business_id": business_id,
            "category": category,
            "key": key,
            "summary_tr": (
                f"Hafıza kaydedildi: [{category}/{key}] = '{value[:60]}'. "
                f"Sebep: {reason}"
            ),
        }
    except Exception as exc:
        log.error(
            "save_sales_memory failed: business=%s category=%s key=%s err=%s",
            business_id, category, key, exc,
        )
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# 2) get_sales_memory
# ---------------------------------------------------------------------------


async def _get_sales_memory_impl(
    business_id: str,
    category: str | None = None,
) -> dict[str, Any]:
    """Bir business için hafıza notlarını oku.

    category None → tüm kategorilerden çek.
    """
    if not business_id or not business_id.strip():
        return {"success": False, "error": "business_id zorunlu."}
    business_id = business_id.strip()

    if category is not None:
        err = _validate_category(category)
        if err:
            return {"success": False, "error": err}
        categories = [category]
    else:
        categories = sorted(VALID_CATEGORIES)

    data: dict[str, list[dict[str, Any]]] = {}
    try:
        for cat in categories:
            doc_client = get_document_client(_notes_path(business_id, cat))
            docs = doc_client.list_documents(limit=500) or []
            notes: list[dict[str, Any]] = []
            for d in docs:
                notes.append({
                    "key": d.get("key") or d.get("documentId"),
                    "value": d.get("value"),
                    "reason": d.get("reason"),
                    "updated_at": d.get("updated_at"),
                })
            if notes:
                data[cat] = notes
    except Exception as exc:
        log.error(
            "get_sales_memory failed: business=%s category=%s err=%s",
            business_id, category, exc,
        )
        return {"success": False, "error": str(exc)}

    if not data:
        return {
            "success": True,
            "data": {},
            "summary_tr": "Bu işletme için kayıtlı hafıza yok.",
        }
    total = sum(len(v) for v in data.values())
    cats_str = ", ".join(f"{k}({len(v)})" for k, v in data.items())
    return {
        "success": True,
        "data": data,
        "summary_tr": f"{total} hafıza notu bulundu: {cats_str}.",
    }


# ---------------------------------------------------------------------------
# 3) delete_sales_memory
# ---------------------------------------------------------------------------


async def _delete_sales_memory_impl(
    business_id: str,
    category: str,
    key: str,
    reason: str,
) -> dict[str, Any]:
    """Bir hafıza notunu sil. reason zorunlu (audit log)."""
    if not business_id or not business_id.strip():
        return {"success": False, "error": "business_id zorunlu."}
    err = _validate_category(category)
    if err:
        return {"success": False, "error": err}
    if not key or len(key.strip()) < 2:
        return {"success": False, "error": "key en az 2 karakter olmalı."}
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "reason en az 5 karakter olmalı."}

    business_id = business_id.strip()
    key = key.strip()
    try:
        doc_client = get_document_client(_notes_path(business_id, category))
        existing = doc_client.get_document(key)
        if not existing:
            log.info(
                "delete_sales_memory: not found business=%s category=%s key=%s",
                business_id, category, key,
            )
            return {
                "success": False,
                "error": f"Not bulunamadı: [{category}/{key}]",
            }
        doc_client.delete_document(key)
        log.info(
            "delete_sales_memory: business=%s category=%s key=%s reason=%s",
            business_id, category, key, reason,
        )
        return {
            "success": True,
            "business_id": business_id,
            "category": category,
            "key": key,
            "summary_tr": (
                f"Hafıza silindi: [{category}/{key}]. Sebep: {reason}"
            ),
        }
    except Exception as exc:
        log.error(
            "delete_sales_memory failed: business=%s category=%s key=%s err=%s",
            business_id, category, key, exc,
        )
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


save_sales_memory = function_tool(
    name_override="save_sales_memory",
    description_override=(
        "Sales Manager structured memory'ye not kaydet. "
        "category: decisions|preferences|learnings|contacts. "
        "REQUIRED: business_id, category, key (>=2 char), value (>=5 char), "
        "reason (>=5 char, audit log için)."
    ),
    strict_mode=False,
)(_save_sales_memory_impl)


get_sales_memory = function_tool(
    name_override="get_sales_memory",
    description_override=(
        "Sales Manager hafızasını oku. category verilmezse 4 kategoriden de "
        "çeker. Returns: {data: {category: [{key, value, reason, "
        "updated_at}]}, summary_tr}."
    ),
    strict_mode=False,
)(_get_sales_memory_impl)


delete_sales_memory = function_tool(
    name_override="delete_sales_memory",
    description_override=(
        "Bir hafıza notunu sil. REQUIRED: business_id, category, key, "
        "reason (>=5 char, audit log)."
    ),
    strict_mode=False,
)(_delete_sales_memory_impl)


def get_sales_memory_tools() -> list:
    """Sales Manager memory tools (save + get + delete)."""
    return [save_sales_memory, get_sales_memory, delete_sales_memory]


__all__ = [
    "VALID_CATEGORIES",
    "save_sales_memory",
    "get_sales_memory",
    "delete_sales_memory",
    "get_sales_memory_tools",
    "_save_sales_memory_impl",
    "_get_sales_memory_impl",
    "_delete_sales_memory_impl",
]
