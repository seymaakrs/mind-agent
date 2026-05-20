"""Guardian (Bekci) status tool — orchestrator agent'a verilir.

Bekci otonom calisir (Cloud Run job, her 30 dk NocoDB Etkilesimler'i
okur, karar verir, system_settings'e yazar). Bu modul Sef (orchestrator)
agent'in Bekci durumunu OKUMASINI saglar.

Kullanim: kullanici "kampanya nasil gidiyor?" / "outreach durdu mu?"
diye sordugunda Sef bu tool'u cagirir, Bekci'nin son kararini
kullaniciya iletir.

NOT: Bu tool SADECE OKUR. Bekci'nin kararini override etmez. Override
gerekirse ayri bir tool (resume_outreach_override) ileride eklenir.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from agents import function_tool

from src.infra.nocodb_client import get_nocodb_client


log = logging.getLogger(__name__)


def _settings_table_id() -> str | None:
    return os.environ.get("NOCODB_SETTINGS_TABLE_ID") or None


# Human readable mapping
_LEVEL_TR = {
    "GREEN": "🟢 SAĞLIKLI",
    "YELLOW": "🟡 UYARI",
    "RED": "🔴 KRİTİK — Outreach DURDURULDU",
    "INSUFFICIENT": "⚪ YETERSİZ VERİ — henüz karar verilemiyor",
}


async def _get_guardian_status_impl() -> dict[str, Any]:
    """Pure implementation — testten dogrudan cagrilir."""
    settings_tbl = _settings_table_id()
    if not settings_tbl:
        return {
            "success": False,
            "error": "NOCODB_SETTINGS_TABLE_ID env yok — Bekci durumu kaydedilmiyor.",
            "configured": False,
        }

    try:
        client = get_nocodb_client()
        rows = client.list_records(settings_tbl, limit=1).get("list") or []
    except Exception as exc:
        log.warning("guardian_status: nocodb read failed: %s", exc)
        return {
            "success": False,
            "error": f"NocoDB okuma hatasi: {type(exc).__name__}",
            "configured": True,
        }

    if not rows:
        return {
            "success": True,
            "configured": True,
            "level": "INSUFFICIENT",
            "summary": "Bekci henuz tick atmadi — Cloud Run job'u baslatildi mi kontrol et.",
        }

    row = rows[0]
    level = row.get("last_decision_level") or "INSUFFICIENT"
    action = row.get("last_recommended_action") or "NONE"
    reason = row.get("last_decision_reason") or ""
    last_check = row.get("last_health_check") or "henuz yok"
    paused = bool(row.get("outreach_paused"))
    pause_reason = row.get("pause_reason") or ""
    paused_at = row.get("paused_at") or ""
    resumed_at = row.get("resumed_at") or ""

    metrics: dict[str, Any] = {}
    raw_metrics = row.get("last_metrics_json")
    if raw_metrics:
        try:
            metrics = json.loads(raw_metrics)
        except Exception:
            metrics = {}

    level_tr = _LEVEL_TR.get(level, level)
    summary_lines = [
        f"Bekci durumu: {level_tr}",
        f"Son kontrol: {last_check}",
    ]
    if reason:
        summary_lines.append(f"Sebep: {reason}")
    if metrics:
        out = metrics.get("outreach_sent")
        inb = metrics.get("inbound_received")
        rr = metrics.get("reply_rate_pct")
        er = metrics.get("engagement_rate_pct")
        summary_lines.append(
            f"Son 24h: {out or 0} outreach giden, {inb or 0} inbound geldi, "
            f"reply_rate %{rr or 0}, engagement_rate %{er or 0}"
        )
    if paused:
        summary_lines.append(
            f"⚠️ Outreach SU AN DURDURULMUS (sebep: {pause_reason}, zamani: {paused_at})"
        )
    elif resumed_at:
        summary_lines.append(f"Outreach aktif (son resume: {resumed_at})")

    return {
        "success": True,
        "configured": True,
        "level": level,
        "recommended_action": action,
        "outreach_paused": paused,
        "pause_reason": pause_reason,
        "paused_at": paused_at,
        "resumed_at": resumed_at,
        "last_health_check": last_check,
        "metrics": metrics,
        "reason_summary": reason,
        "summary": "\n".join(summary_lines),
    }


get_guardian_status = function_tool(
    name_override="get_guardian_status",
    description_override=(
        "Bekci (Guardian) agent'in son saglik kararini ve metriklerini NocoDB'den "
        "okur. Outreach kampanyasi su an pause edilmis mi, son reply_rate/"
        "engagement_rate ne, hangi seviye (GREEN/YELLOW/RED) — hepsi tek call'da. "
        "Kullanici 'kampanya nasil', 'outreach calisiyor mu', 'Bekci durumu' diye "
        "sordugunda bunu cagir. SADECE OKUR, override etmez."
    ),
)(_get_guardian_status_impl)


def get_guardian_tools() -> list:
    return [get_guardian_status]


__all__ = [
    "get_guardian_status",
    "get_guardian_tools",
    "_get_guardian_status_impl",
]
