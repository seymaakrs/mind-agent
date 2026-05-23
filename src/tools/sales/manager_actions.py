"""Sales Manager YAZMA aksiyonları (TODO A — 5 tool).

Satış Müdürü artık sadece okumakla kalmaz, NocoDB'ye karar yazar:
  1. outreach_pause / outreach_resume — kampanyayı durdur/devam et
  2. lead_reassign — lead'i başkasına ata
  3. lead_priority_set — lead önceliğini değiştir
  4. auto_reply_template_update — DM cevap template'ini güncelle
  5. outreach_daily_limit_set — günlük gönderim limitini ayarla

HER AKSIYON `manager_actions` tablosuna audit-log olarak yazılır:
  - kim yaptı (sales_manager)
  - ne yaptı (action_type)
  - neden (reason — Müdür her aksiyon icin gerekce verir)
  - ne zaman (CreatedAt otomatik)
  - sonuç (succeeded/failed)

Müdür yanlış aksiyon alırsa: log'tan görülür, manuel geri alınır.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.errors import classify_error
from src.infra.nocodb_client import NocoDBClient

log = logging.getLogger(__name__)


def get_nocodb_client() -> NocoDBClient:
    """Lazy singleton (test'ten patch'lemek için modül seviyesi)."""
    from src.tools.sales.reporting_tools import get_nocodb_client as _g
    return _g()


def _leads_table() -> str | None:
    return os.environ.get("NOCODB_LEADS_TABLE_ID")


def _settings_table() -> str | None:
    return os.environ.get("NOCODB_SETTINGS_TABLE_ID")


def _templates_table() -> str | None:
    """`message_templates` tablo id'si."""
    return os.environ.get("NOCODB_TEMPLATES_TABLE_ID")


def _actions_log_table() -> str | None:
    """Müdür aksiyonlarının audit log'u (yoksa best-effort, hata değil)."""
    return os.environ.get("NOCODB_MANAGER_ACTIONS_TABLE_ID")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(
    action_type: str,
    target: str,
    reason: str,
    details: dict[str, Any],
    result: str,
) -> None:
    """Best-effort audit log. Tablo yoksa log'a düşer, çağrı durmaz."""
    tbl = _actions_log_table()
    if not tbl:
        log.info(
            "manager_action audit: type=%s target=%s reason=%s result=%s details=%s",
            action_type, target, reason, result, json.dumps(details, ensure_ascii=False),
        )
        return
    try:
        client = get_nocodb_client()
        client.create_record(tbl, {
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "details_json": json.dumps(details, ensure_ascii=False),
            "result": result,
            "actor": "sales_manager",
            "occurred_at": _now_iso(),
        })
    except Exception as exc:
        log.warning("manager_action audit failed: %s", exc)


# ---------------------------------------------------------------------------
# 1) outreach_pause / outreach_resume
# ---------------------------------------------------------------------------


async def _outreach_pause_impl(reason: str) -> dict[str, Any]:
    """Outreach kampanyasını DURDUR. system_settings.outreach_paused = true.
    Avcı bir sonraki tick'te bayrağı okur, mesaj atmayı keser.
    """
    tbl = _settings_table()
    if not tbl:
        return {"success": False, "error": "NOCODB_SETTINGS_TABLE_ID yok."}
    if not reason or len(reason.strip()) < 5:
        return {
            "success": False,
            "error": "Sebep en az 5 karakter olmalı (audit log için zorunlu).",
        }
    try:
        client = get_nocodb_client()
        rows = client.list_records(tbl, limit=1).get("list") or []
        if not rows:
            return {"success": False, "error": "system_settings boş."}
        row_id = rows[0].get("Id")
        client.update_record(tbl, row_id, {
            "outreach_paused": True,
            "pause_reason": reason,
            "paused_at": _now_iso(),
        })
        _audit("outreach_pause", "outreach_campaign", reason, {}, "ok")
        return {
            "success": True,
            "action": "paused",
            "reason": reason,
            "summary_tr": f"Outreach kampanyası DURDURULDU. Sebep: {reason}",
        }
    except Exception as exc:
        _audit("outreach_pause", "outreach_campaign", reason, {"err": str(exc)}, "fail")
        return classify_error(exc, "nocodb")


async def _outreach_resume_impl(reason: str) -> dict[str, Any]:
    """Outreach kampanyasını YENIDEN BAŞLAT. Bekçi RED'den çıkmış olmalı."""
    tbl = _settings_table()
    if not tbl:
        return {"success": False, "error": "NOCODB_SETTINGS_TABLE_ID yok."}
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmalı."}
    try:
        client = get_nocodb_client()
        rows = client.list_records(tbl, limit=1).get("list") or []
        if not rows:
            return {"success": False, "error": "system_settings boş."}
        row_id = rows[0].get("Id")
        client.update_record(tbl, row_id, {
            "outreach_paused": False,
            "pause_reason": None,
            "resumed_at": _now_iso(),
        })
        _audit("outreach_resume", "outreach_campaign", reason, {}, "ok")
        return {
            "success": True,
            "action": "resumed",
            "summary_tr": f"Outreach kampanyası DEVAM EDİYOR. Sebep: {reason}",
        }
    except Exception as exc:
        _audit("outreach_resume", "outreach_campaign", reason, {"err": str(exc)}, "fail")
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# 2) lead_reassign
# ---------------------------------------------------------------------------


async def _lead_reassign_impl(
    lead_id: int | str,
    new_owner: str,
    reason: str,
) -> dict[str, Any]:
    """Lead'i başka bir satışçıya ata. NocoDB Leadler.atanan_kisi update."""
    tbl = _leads_table()
    if not tbl:
        return {"success": False, "error": "NOCODB_LEADS_TABLE_ID yok."}
    if not new_owner or len(new_owner.strip()) < 2:
        return {"success": False, "error": "new_owner zorunlu."}
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmalı."}
    try:
        client = get_nocodb_client()
        client.update_record(tbl, lead_id, {
            "atanan_kisi": new_owner,
            "reassigned_at": _now_iso(),
        })
        _audit(
            "lead_reassign", f"lead:{lead_id}", reason,
            {"new_owner": new_owner}, "ok",
        )
        return {
            "success": True,
            "lead_id": lead_id,
            "new_owner": new_owner,
            "summary_tr": f"Lead #{lead_id} → {new_owner}. Sebep: {reason}",
        }
    except Exception as exc:
        _audit("lead_reassign", f"lead:{lead_id}", reason, {"err": str(exc)}, "fail")
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# 3) lead_priority_set
# ---------------------------------------------------------------------------


VALID_PRIORITIES = {"acil", "yuksek", "normal", "dusuk"}


async def _lead_priority_set_impl(
    lead_id: int | str,
    priority: str,
    reason: str,
) -> dict[str, Any]:
    """Lead önceliğini değiştir. Avcı bir sonraki batch'te yüksek önceliklilere
    öncelik verir (mevcut lead_skoru sıralamasının üstüne eklenir).
    """
    tbl = _leads_table()
    if not tbl:
        return {"success": False, "error": "NOCODB_LEADS_TABLE_ID yok."}
    pri = (priority or "").strip().lower()
    if pri not in VALID_PRIORITIES:
        return {
            "success": False,
            "error": f"Geçersiz priority. Geçerli: {sorted(VALID_PRIORITIES)}",
        }
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmalı."}
    try:
        client = get_nocodb_client()
        client.update_record(tbl, lead_id, {
            "priority": pri,
            "priority_set_at": _now_iso(),
        })
        _audit(
            "lead_priority_set", f"lead:{lead_id}", reason,
            {"priority": pri}, "ok",
        )
        return {
            "success": True,
            "lead_id": lead_id,
            "priority": pri,
            "summary_tr": f"Lead #{lead_id} → priority={pri}. Sebep: {reason}",
        }
    except Exception as exc:
        _audit(
            "lead_priority_set", f"lead:{lead_id}", reason,
            {"err": str(exc)}, "fail",
        )
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# 4) auto_reply_template_update
# ---------------------------------------------------------------------------


async def _auto_reply_template_update_impl(
    intent: str,
    new_text: str,
    reason: str,
) -> dict[str, Any]:
    """DM Yanıtlayıcı'nın template'ini güncelle.

    intent: 'olumlu' | 'olumsuz' | 'soru' | 'spam' | 'itiraz' (mevcut intent'ler)
    new_text: yeni cevap metni (Türkçe, Slowdays tonu)
    """
    tbl = _templates_table()
    if not tbl:
        return {
            "success": False,
            "error": "NOCODB_TEMPLATES_TABLE_ID yok — template tablosu kurulmamış.",
        }
    if not intent or not new_text or len(new_text.strip()) < 10:
        return {
            "success": False,
            "error": "intent ve new_text (>=10 char) zorunlu.",
        }
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmalı."}
    try:
        client = get_nocodb_client()
        # Intent'e göre kayıt bul, yoksa yarat
        existing = client.find_by_field(tbl, "intent", intent)
        if existing and isinstance(existing, dict):
            client.update_record(tbl, existing.get("Id"), {
                "text": new_text,
                "updated_at": _now_iso(),
            })
            op = "updated"
        else:
            client.create_record(tbl, {
                "intent": intent,
                "text": new_text,
                "created_at": _now_iso(),
            })
            op = "created"
        _audit(
            "auto_reply_template_update", f"intent:{intent}", reason,
            {"new_text_preview": new_text[:80], "op": op}, "ok",
        )
        return {
            "success": True,
            "intent": intent,
            "operation": op,
            "summary_tr": (
                f"Auto-reply template '{intent}' {op}. Sebep: {reason}. "
                f"Yeni metin: {new_text[:80]}..."
            ),
        }
    except Exception as exc:
        _audit(
            "auto_reply_template_update", f"intent:{intent}", reason,
            {"err": str(exc)}, "fail",
        )
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# 5) outreach_daily_limit_set
# ---------------------------------------------------------------------------


async def _outreach_daily_limit_set_impl(
    new_limit: int,
    reason: str,
) -> dict[str, Any]:
    """Günlük outreach mesaj limitini değiştir. Ban riskine göre düşür/artır."""
    tbl = _settings_table()
    if not tbl:
        return {"success": False, "error": "NOCODB_SETTINGS_TABLE_ID yok."}
    if not isinstance(new_limit, int) or new_limit < 0 or new_limit > 2000:
        return {
            "success": False,
            "error": "new_limit 0-2000 arası int olmalı.",
        }
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmalı."}
    try:
        client = get_nocodb_client()
        rows = client.list_records(tbl, limit=1).get("list") or []
        if not rows:
            return {"success": False, "error": "system_settings boş."}
        row_id = rows[0].get("Id")
        old_limit = rows[0].get("outreach_daily_limit")
        client.update_record(tbl, row_id, {
            "outreach_daily_limit": new_limit,
            "limit_changed_at": _now_iso(),
        })
        _audit(
            "outreach_daily_limit_set", "outreach_campaign", reason,
            {"old": old_limit, "new": new_limit}, "ok",
        )
        return {
            "success": True,
            "old_limit": old_limit,
            "new_limit": new_limit,
            "summary_tr": (
                f"Günlük outreach limiti {old_limit} → {new_limit}. "
                f"Sebep: {reason}"
            ),
        }
    except Exception as exc:
        _audit(
            "outreach_daily_limit_set", "outreach_campaign", reason,
            {"err": str(exc)}, "fail",
        )
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


outreach_pause = function_tool(
    name_override="outreach_pause",
    description_override=(
        "Outreach kampanyasını ANINDA DURDUR. system_settings.outreach_paused=true. "
        "Bekçi alarmda, ban riski sezdiğinde, kalite düştüğünde kullan. "
        "REQUIRED: reason (>=5 karakter, audit log için)."
    ),
    strict_mode=False,
)(_outreach_pause_impl)


outreach_resume = function_tool(
    name_override="outreach_resume",
    description_override=(
        "Durdurulmuş outreach kampanyasını yeniden başlat. "
        "Bekçi yeşile dönmüş, sebep ortadan kalkmış olmalı. "
        "REQUIRED: reason (>=5 karakter)."
    ),
    strict_mode=False,
)(_outreach_resume_impl)


lead_reassign = function_tool(
    name_override="lead_reassign",
    description_override=(
        "Lead'i başka satışçıya ata (atanan_kisi field'ını değiştir). "
        "Şeyma müsait değilse Beyza'ya, vs. "
        "REQUIRED: lead_id (int), new_owner (str, örn. 'Beyza'), reason (>=5 char)."
    ),
    strict_mode=False,
)(_lead_reassign_impl)


lead_priority_set = function_tool(
    name_override="lead_priority_set",
    description_override=(
        "Lead önceliğini değiştir: acil | yuksek | normal | dusuk. "
        "Acil olanlar Avcı'nın sonraki batch'inde ilk sırada gider. "
        "REQUIRED: lead_id, priority, reason (>=5 char)."
    ),
    strict_mode=False,
)(_lead_priority_set_impl)


auto_reply_template_update = function_tool(
    name_override="auto_reply_template_update",
    description_override=(
        "DM Yanıtlayıcı'nın intent'e göre cevap template'ini güncelle. "
        "Reply rate düşükse template'i yumuşat / sertleştir. "
        "REQUIRED: intent (olumlu|olumsuz|soru|spam|itiraz), new_text (>=10 char), reason."
    ),
    strict_mode=False,
)(_auto_reply_template_update_impl)


outreach_daily_limit_set = function_tool(
    name_override="outreach_daily_limit_set",
    description_override=(
        "Günlük outreach mesaj limitini değiştir (varsayılan 240). "
        "Ban riski varsa düşür, hız gerekiyorsa artır (max 2000). "
        "REQUIRED: new_limit (0-2000 int), reason (>=5 char)."
    ),
    strict_mode=False,
)(_outreach_daily_limit_set_impl)


def get_manager_action_tools() -> list:
    """Sales Manager'a verilecek 6 yazma aksiyon tool'u."""
    return [
        outreach_pause,
        outreach_resume,
        lead_reassign,
        lead_priority_set,
        auto_reply_template_update,
        outreach_daily_limit_set,
    ]


__all__ = [
    "outreach_pause",
    "outreach_resume",
    "lead_reassign",
    "lead_priority_set",
    "auto_reply_template_update",
    "outreach_daily_limit_set",
    "get_manager_action_tools",
    # impl exports for testing
    "_outreach_pause_impl",
    "_outreach_resume_impl",
    "_lead_reassign_impl",
    "_lead_priority_set_impl",
    "_auto_reply_template_update_impl",
    "_outreach_daily_limit_set_impl",
]
