"""Brand Identity tools (Faz A.2, 2026-05-12).

Mind-id Sales OS — kanonik marka kimligi okuma/yazma araclari.

Yapi:
  - ``load_brand_identity(business_id)``  -> pure Python, dahili kullanım
  - ``save_brand_identity(business_id, brand_identity)`` -> pure Python
  - ``fetch_brand_identity`` (function_tool) -> agent'lara verilir
  - ``update_brand_identity`` (function_tool) -> agent'lara verilir
  - ``brand_identity_exists(business_id)`` -> hizli kontrol

Firestore path: ``businesses/{business_id}/brand_identity/v1``

Geri uyum: bu modul tamamen ADDITIVE. Eski ``businesses/{id}.profile`` field
aynen okunmaya devam eder. Agent'lar brand_identity yoksa eski yola dusebilir.
"""
from __future__ import annotations

import logging
from typing import Any

from agents import function_tool

from src.infra.brand_identity import (
    BRAND_IDENTITY_SCHEMA_VERSION,
    BrandIdentity,
)
from src.infra.firebase_client import get_document_client


log = logging.getLogger(__name__)

# Subcollection naming — versiyon tutarli olsun diye 'v1' document id
_BRAND_DOC_ID = "v1"


def _brand_collection_path(business_id: str) -> str:
    return f"businesses/{business_id}/brand_identity"


# ---------------------------------------------------------------------------
# Pure helpers (testten/agent'tan/script'ten cagrilabilir)
# ---------------------------------------------------------------------------


def load_brand_identity(business_id: str) -> BrandIdentity | None:
    """Firestore'dan brand identity'i yukler.

    Returns:
        BrandIdentity obj ise dolu, None ise hic yok (henuz olusturulmamis).
        Validation hatasinda da None doner + log (eski sema kaldi varsayim).
    """
    if not business_id:
        return None
    try:
        doc_client = get_document_client(_brand_collection_path(business_id))
        data = doc_client.get_document(_BRAND_DOC_ID)
        if not data:
            return None
        # Firestore otomatik 'documentId' ekliyor — Pydantic 'extra=forbid'
        # ile bunu reddeder, temizle.
        data.pop("documentId", None)
        return BrandIdentity.model_validate(data)
    except Exception as exc:
        log.warning(
            "load_brand_identity: business=%s read/parse failed: %s",
            business_id, exc,
        )
        return None


def save_brand_identity(brand_identity: BrandIdentity) -> dict[str, Any]:
    """BrandIdentity'i Firestore'a yazar (merge=False, tam degisim).

    Returns:
        dict: {'success', 'business_id', 'schema_version', 'updated_at'}
    """
    try:
        doc_client = get_document_client(
            _brand_collection_path(brand_identity.business_id)
        )
        # model_dump mode='json' tarihleri ISO string yapar — Firestore OK
        data = brand_identity.model_dump(mode="json")
        doc_client.set_document(_BRAND_DOC_ID, data, merge=False)
        return {
            "success": True,
            "business_id": brand_identity.business_id,
            "schema_version": brand_identity.schema_version,
            "updated_at": data["updated_at"],
        }
    except Exception as exc:
        log.error(
            "save_brand_identity: business=%s save failed: %s",
            brand_identity.business_id, exc,
        )
        return {
            "success": False,
            "error": str(exc),
            "business_id": brand_identity.business_id,
        }


def brand_identity_exists(business_id: str) -> bool:
    """Hizli kontrol: bu business icin brand identity yazilmis mi?"""
    return load_brand_identity(business_id) is not None


# ---------------------------------------------------------------------------
# Agent-facing function_tool wrapper'lari
# ---------------------------------------------------------------------------


async def _fetch_brand_identity_impl(business_id: str) -> dict[str, Any]:
    """Implementation — testten dogrudan cagrilir."""
    if not business_id or not business_id.strip():
        return {
            "success": False,
            "error": "business_id is required",
            "exists": False,
        }
    bi = load_brand_identity(business_id.strip())
    if bi is None:
        return {
            "success": True,
            "business_id": business_id,
            "exists": False,
            "message": (
                "Brand identity henuz olusturulmamis. fetch_business "
                "kullanarak eski profile field'ina dusebilirsin."
            ),
        }
    data = bi.model_dump(mode="json")
    return {
        "success": True,
        "exists": True,
        "is_substantially_filled": bi.is_substantially_filled(),
        "prompt_summary": bi.prompt_summary(),
        **data,
    }


async def _update_brand_identity_impl(
    business_id: str,
    fields: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Implementation — testten dogrudan cagrilir."""
    if not business_id or not business_id.strip():
        return {"success": False, "error": "business_id is required"}
    fields = fields or {}

    existing = load_brand_identity(business_id.strip())
    if existing is None:
        base: dict[str, Any] = {
            "business_id": business_id.strip(),
            "schema_version": BRAND_IDENTITY_SCHEMA_VERSION,
        }
        if source:
            base["source"] = source
        base.update(fields)
        try:
            bi = BrandIdentity.model_validate(base)
        except Exception as exc:
            return {"success": False, "error": f"validation: {exc}"}
    else:
        merged = existing.model_dump(mode="json")
        for k, v in fields.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        if source:
            merged["source"] = source
        merged.pop("documentId", None)
        try:
            bi = BrandIdentity.model_validate(merged)
        except Exception as exc:
            return {"success": False, "error": f"validation: {exc}"}

    return save_brand_identity(bi)


fetch_brand_identity = function_tool(
    name_override="fetch_brand_identity",
    description_override=(
        "Fetch business brand identity (BrandIdentity Pydantic schema) from "
        "Firestore. Returns: name, tagline, industry, primary_colors, "
        "visual_style, photography_style, voice tone, avoid_words, "
        "preferred_words, audience, content strategy, business_context, "
        "and a `prompt_summary` field that is a compact string Image/Video/"
        "Marketing agents should inject into their prompts. If no brand "
        "identity exists yet, returns {success: True, exists: False} so the "
        "caller can fall back to fetch_business `profile` field."
    ),
)(_fetch_brand_identity_impl)


update_brand_identity = function_tool(
    name_override="update_brand_identity",
    description_override=(
        "Update business brand identity in Firestore. Args: business_id, "
        "fields (partial dict — merged into existing brand_identity). "
        "Allowed field keys: basics, visual, voice, audience, "
        "content_strategy, business_context. Uses Pydantic validation; "
        "invalid hex colors / unknown fields rejected with 422-style error. "
        "Source defaults to 'manual'; set source='ai_synthesis' or 'draft' "
        "for non-human updates."
    ),
    strict_mode=False,
)(_update_brand_identity_impl)


def get_brand_tools() -> list:
    """All brand identity tools (read + write)."""
    return [fetch_brand_identity, update_brand_identity]


__all__ = [
    "load_brand_identity",
    "save_brand_identity",
    "brand_identity_exists",
    "fetch_brand_identity",
    "update_brand_identity",
    "_fetch_brand_identity_impl",
    "_update_brand_identity_impl",
    "get_brand_tools",
]
