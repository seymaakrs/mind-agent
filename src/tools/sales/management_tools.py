"""Sales Director (Satis Direktoru) management tools — write authority.

Faz 1 yukseltmesi (eski Sales Manager -> Sales Director). Direktor su yazma
yetkilerine sahip:

- Outreach pause/resume (eskiden reporting_tools.py icindeydi, buraya tasindi)
- Auto-reply pause/resume (yeni — runner ayni bayragi okuyacak)
- Lead writes: assign_lead, update_lead_stage, add_lead_note
- Pipeline forecast (Firsatlar tablosu — weighted)
- Weekly KPI (sicak + kazanildi hedef vs gercek)

Faz 2 (alt muduurler) ileride. Su an tum yetki Direktor'de toplu.

Schema notlari:
- Leadler.asama valid degerleri: Yeni|Soguk|Ilik|Sicak|Teklif|Sozlesme|
  Kazanildi|Kayip|Arsiv|Takipte|Itiraz.
- Firsatlar tablosu (env NOCODB_FIRSATLAR_TABLE_ID, default mnf5nyu2mx5xtej).
  Sahalar (CLAUDE.md devir notundan): asama (Teklif|Sozlesme|Kazanildi|Kayip),
  tutar (Currency/Number).
- system_settings tek satir tabloda (Id=1) - outreach_paused + auto_reply_paused
  bayraklari + ilgili reason / timestamp kolonlari.
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from agents import function_tool

from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client
from src.tools.sales.reporting_tools import (
    _fetch_all,
    _missing_table_error,
    _leads_table,
    _settings_table,
)


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


VALID_LEAD_STAGES = {
    "Yeni",
    "Soguk",
    "Ilik",
    "Sicak",
    "Teklif",
    "Sozlesme",
    "Kazanildi",
    "Kayip",
    "Arsiv",
    "Takipte",
    "Itiraz",
}

DEAL_STAGE_WEIGHTS = {
    "Teklif": 0.3,
    "Sozlesme": 0.7,
    "Kazanildi": 1.0,
}

OPEN_DEAL_STAGES = ("Teklif", "Sozlesme")
WON_DEAL_STAGE = "Kazanildi"

# Default from CLAUDE.md devir notu (Upsell/Referans n8n workflow'larinin
# kullandigi tablo). Env override: NOCODB_FIRSATLAR_TABLE_ID.
DEFAULT_FIRSATLAR_TABLE_ID = "mnf5nyu2mx5xtej"


def _firsatlar_table() -> str:
    return os.environ.get("NOCODB_FIRSATLAR_TABLE_ID") or DEFAULT_FIRSATLAR_TABLE_ID


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _today_date_iso() -> str:
    return _now_utc().date().isoformat()


# ---------------------------------------------------------------------------
# Outreach pause / resume (moved from reporting_tools)
# ---------------------------------------------------------------------------


async def _outreach_pause_impl(reason: str) -> dict[str, Any]:
    tbl = _settings_table()
    if not tbl:
        return _missing_table_error("settings")
    try:
        now_iso = _now_iso()
        get_nocodb_client().update_record(
            tbl,
            1,
            {
                "outreach_paused": True,
                "pause_reason": reason,
                "paused_at": now_iso,
            },
        )
        return {
            "success": True,
            "paused": True,
            "reason": reason,
            "paused_at": now_iso,
            "summary_tr": f"Outreach durduruldu. Sebep: {reason}",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _outreach_resume_impl() -> dict[str, Any]:
    tbl = _settings_table()
    if not tbl:
        return _missing_table_error("settings")
    try:
        now_iso = _now_iso()
        get_nocodb_client().update_record(
            tbl,
            1,
            {
                "outreach_paused": False,
                "pause_reason": "",
                "resumed_at": now_iso,
            },
        )
        return {
            "success": True,
            "paused": False,
            "resumed_at": now_iso,
            "summary_tr": "Outreach yeniden baslatildi. Kampanya devam ediyor.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Auto-reply pause / resume (1.6 — new)
# ---------------------------------------------------------------------------


async def _auto_reply_pause_impl(reason: str) -> dict[str, Any]:
    tbl = _settings_table()
    if not tbl:
        return _missing_table_error("settings")
    try:
        now_iso = _now_iso()
        get_nocodb_client().update_record(
            tbl,
            1,
            {
                "auto_reply_paused": True,
                "auto_reply_pause_reason": reason,
                "auto_reply_paused_at": now_iso,
            },
        )
        return {
            "success": True,
            "paused": True,
            "reason": reason,
            "paused_at": now_iso,
            "summary_tr": f"Auto-reply durduruldu. Sebep: {reason}",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _auto_reply_resume_impl() -> dict[str, Any]:
    tbl = _settings_table()
    if not tbl:
        return _missing_table_error("settings")
    try:
        now_iso = _now_iso()
        get_nocodb_client().update_record(
            tbl,
            1,
            {
                "auto_reply_paused": False,
                "auto_reply_pause_reason": "",
                "auto_reply_resumed_at": now_iso,
            },
        )
        return {
            "success": True,
            "paused": False,
            "resumed_at": now_iso,
            "summary_tr": "Auto-reply yeniden baslatildi.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Lead writes (1.3-1.5)
# ---------------------------------------------------------------------------


def _invalid_stage_error(stage: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": f"Invalid asama '{stage}'. Allowed: {sorted(VALID_LEAD_STAGES)}",
        "error_code": "INVALID_INPUT",
        "service": "nocodb",
        "retryable": False,
        "user_message_tr": (
            f"Gecersiz asama: '{stage}'. Izinli degerler: "
            + ", ".join(sorted(VALID_LEAD_STAGES))
        ),
    }


async def _assign_lead_impl(lead_id: int, atanan_kisi: str) -> dict[str, Any]:
    """Update Leadler.atanan_kisi for a lead."""
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    if not atanan_kisi or not atanan_kisi.strip():
        return {
            "success": False,
            "error": "atanan_kisi required.",
            "error_code": "INVALID_INPUT",
            "retryable": False,
            "user_message_tr": "atanan_kisi bos olamaz.",
        }
    try:
        record = get_nocodb_client().update_record(
            table_id, lead_id, {"atanan_kisi": atanan_kisi.strip()}
        )
        return {
            "success": True,
            "lead_id": lead_id,
            "atanan_kisi": atanan_kisi.strip(),
            "record": record,
            "summary_tr": f"Lead #{lead_id} -> {atanan_kisi.strip()} kisisine atandi.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _update_lead_stage_impl(
    lead_id: int, asama: str, reason: str = ""
) -> dict[str, Any]:
    """Update Leadler.asama. Optionally append reason to notlar."""
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    if asama not in VALID_LEAD_STAGES:
        return _invalid_stage_error(asama)

    client = get_nocodb_client()
    fields: dict[str, Any] = {"asama": asama}

    if reason and reason.strip():
        try:
            existing = client.get_record(table_id, lead_id) or {}
            old_notes = existing.get("notlar") or ""
            stamp = _today_date_iso()
            appended = f"[{stamp}] {reason.strip()}"
            new_notes = (old_notes + "\n" + appended).strip() if old_notes else appended
            fields["notlar"] = new_notes
        except Exception as exc:
            log.warning(
                "update_lead_stage: notlar read failed lead=%s: %s — proceeding without note",
                lead_id, exc,
            )

    try:
        record = client.update_record(table_id, lead_id, fields)
        return {
            "success": True,
            "lead_id": lead_id,
            "asama": asama,
            "reason": reason or None,
            "record": record,
            "summary_tr": (
                f"Lead #{lead_id} asama -> {asama}"
                + (f" (sebep: {reason.strip()})" if reason and reason.strip() else "")
                + "."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _add_lead_note_impl(lead_id: int, note: str) -> dict[str, Any]:
    """Append timestamped note to Leadler.notlar (read-modify-write)."""
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    if not note or not note.strip():
        return {
            "success": False,
            "error": "note required.",
            "error_code": "INVALID_INPUT",
            "retryable": False,
            "user_message_tr": "Bos not eklenemez.",
        }
    client = get_nocodb_client()
    try:
        existing = client.get_record(table_id, lead_id) or {}
    except Exception as exc:
        return classify_error(exc, "nocodb")

    old_notes = existing.get("notlar") or ""
    stamp = _today_date_iso()
    appended = f"[{stamp}] {note.strip()}"
    new_notes = (old_notes + "\n" + appended).strip() if old_notes else appended

    try:
        record = client.update_record(table_id, lead_id, {"notlar": new_notes})
        return {
            "success": True,
            "lead_id": lead_id,
            "note": note.strip(),
            "notlar": new_notes,
            "record": record,
            "summary_tr": f"Lead #{lead_id} icin not eklendi.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Pipeline forecast (1.7)
# ---------------------------------------------------------------------------


def _coerce_amount(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return 0.0
    return 0.0


async def _pipeline_forecast_impl() -> dict[str, Any]:
    """Sum Firsatlar.tutar per asama + weighted forecast."""
    table_id = _firsatlar_table()
    if not table_id:
        return _missing_table_error("firsatlar")
    try:
        rows = _fetch_all(table_id)
    except Exception as exc:
        return classify_error(exc, "nocodb")

    by_stage: dict[str, dict[str, Any]] = {}
    for r in rows:
        stage = r.get("asama") or "Bilinmeyen"
        amt = _coerce_amount(r.get("tutar"))
        bucket = by_stage.setdefault(stage, {"asama": stage, "count": 0, "total": 0.0})
        bucket["count"] += 1
        bucket["total"] += amt

    weighted = 0.0
    for stage, weight in DEAL_STAGE_WEIGHTS.items():
        weighted += by_stage.get(stage, {}).get("total", 0.0) * weight

    total_open = sum(
        by_stage.get(s, {}).get("total", 0.0) for s in OPEN_DEAL_STAGES
    )
    total_won = by_stage.get(WON_DEAL_STAGE, {}).get("total", 0.0)

    by_stage_list = sorted(by_stage.values(), key=lambda x: x["total"], reverse=True)

    return {
        "success": True,
        "type": "pipeline_forecast",
        "total_open": round(total_open, 2),
        "total_won": round(total_won, 2),
        "weighted_forecast": round(weighted, 2),
        "by_stage": [
            {"asama": b["asama"], "count": b["count"], "total": round(b["total"], 2)}
            for b in by_stage_list
        ],
        "summary_tr": (
            f"Acik pipeline {total_open:.0f} TL, Kazanildi {total_won:.0f} TL, "
            f"agirlikli tahmin {weighted:.0f} TL "
            f"(Teklif×0.3 + Sozlesme×0.7 + Kazanildi×1.0)."
        ),
    }


# ---------------------------------------------------------------------------
# Weekly KPI (1.8)
# ---------------------------------------------------------------------------


def _week_start_utc(now: datetime | None = None) -> datetime:
    n = now or _now_utc()
    monday = n - timedelta(days=n.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def _weekly_kpi_impl(
    target_sicak: int, target_kazanildi: int
) -> dict[str, Any]:
    """Current week (Monday->today UTC) Sicak + Kazanildi counts vs targets."""
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")

    now = _now_utc()
    week_start = _week_start_utc(now)
    week_start_date = week_start.date().isoformat()
    today_date = now.date().isoformat()

    client = get_nocodb_client()
    try:
        # exactDate filter (NocoDB v2 datetime quirk - see reporting_tools)
        sicak_where = (
            f"(asama,eq,Sicak)~and(CreatedAt,ge,exactDate,{week_start_date})"
            f"~and(CreatedAt,le,exactDate,{today_date})"
        )
        kaz_where = (
            f"(asama,eq,Kazanildi)~and(CreatedAt,ge,exactDate,{week_start_date})"
            f"~and(CreatedAt,le,exactDate,{today_date})"
        )
        actual_sicak = client.count_records(table_id, where=sicak_where)
        actual_kazanildi = client.count_records(table_id, where=kaz_where)
    except Exception as exc:
        return classify_error(exc, "nocodb")

    def _pct(num: int, den: int) -> float:
        return round(100.0 * num / den, 1) if den else 0.0

    sicak_pct = _pct(actual_sicak, target_sicak)
    kaz_pct = _pct(actual_kazanildi, target_kazanildi)

    return {
        "success": True,
        "type": "weekly_kpi",
        "week_start": week_start_date,
        "target_sicak": target_sicak,
        "actual_sicak": actual_sicak,
        "target_kazanildi": target_kazanildi,
        "actual_kazanildi": actual_kazanildi,
        "sicak_pct": sicak_pct,
        "kazanildi_pct": kaz_pct,
        "summary_tr": (
            f"Hafta ({week_start_date}->{today_date}): Sicak {actual_sicak}/"
            f"{target_sicak} (%{sicak_pct}), Kazanildi {actual_kazanildi}/"
            f"{target_kazanildi} (%{kaz_pct})."
        ),
    }


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


outreach_pause = function_tool(
    name_override="outreach_pause",
    description_override=(
        "Outreach Robotu'nu DURDUR. system_settings.outreach_paused=True. "
        "REQUIRED: reason (kisa Turkce aciklama)."
    ),
    strict_mode=False,
)(_outreach_pause_impl)


outreach_resume = function_tool(
    name_override="outreach_resume",
    description_override=(
        "Outreach Robotu'nu YENIDEN BASLAT. system_settings.outreach_paused=False. "
        "Argumansiz."
    ),
    strict_mode=False,
)(_outreach_resume_impl)


auto_reply_pause = function_tool(
    name_override="auto_reply_pause",
    description_override=(
        "Auto-reply Robotu'nu DURDUR. system_settings.auto_reply_paused=True. "
        "Auto-reply runner her tick basinda bu bayragi okur, pause edildiyse "
        "yeni mesaj islemez. REQUIRED: reason."
    ),
    strict_mode=False,
)(_auto_reply_pause_impl)


auto_reply_resume = function_tool(
    name_override="auto_reply_resume",
    description_override=(
        "Auto-reply Robotu'nu YENIDEN BASLAT. system_settings.auto_reply_paused=False. "
        "Argumansiz."
    ),
    strict_mode=False,
)(_auto_reply_resume_impl)


assign_lead = function_tool(
    name_override="assign_lead",
    description_override=(
        "Bir lead'i bir kisiye ata. REQUIRED: lead_id (int), atanan_kisi (str). "
        "Leadler.atanan_kisi field'ini gunceller."
    ),
    strict_mode=False,
)(_assign_lead_impl)


update_lead_stage = function_tool(
    name_override="update_lead_stage",
    description_override=(
        "Bir lead'in asama'sini guncelle. REQUIRED: lead_id (int), asama. "
        "Gecerli asama: Yeni|Soguk|Ilik|Sicak|Teklif|Sozlesme|Kazanildi|Kayip|"
        "Arsiv|Takipte|Itiraz. Gecersiz asama reddedilir. OPTIONAL: reason — "
        "verilirse Leadler.notlar field'ine '[YYYY-MM-DD] reason' olarak eklenir."
    ),
    strict_mode=False,
)(_update_lead_stage_impl)


add_lead_note = function_tool(
    name_override="add_lead_note",
    description_override=(
        "Bir lead'in notlar field'ine zaman damgali not ekle (read-modify-write). "
        "REQUIRED: lead_id (int), note (str). Mevcut notlar korunur."
    ),
    strict_mode=False,
)(_add_lead_note_impl)


pipeline_forecast = function_tool(
    name_override="pipeline_forecast",
    description_override=(
        "Firsatlar tablosundaki acik anlasmalarin tutarini asama bazinda topla "
        "+ agirlikli tahmin uret. Agirlik: Teklif×0.3 + Sozlesme×0.7 + "
        "Kazanildi×1.0. Argumansiz. Returns {total_open, total_won, "
        "weighted_forecast, by_stage, summary_tr}."
    ),
    strict_mode=False,
)(_pipeline_forecast_impl)


weekly_kpi = function_tool(
    name_override="weekly_kpi",
    description_override=(
        "Bu hafta (Pazartesi UTC -> bugun) Sicak + Kazanildi lead sayilarini "
        "hedef ile karsilastir. REQUIRED: target_sicak (int), target_kazanildi (int). "
        "Returns {week_start, target_*, actual_*, *_pct, summary_tr}."
    ),
    strict_mode=False,
)(_weekly_kpi_impl)


def get_management_tools() -> list:
    """Sales Director'un tum yazma + ust seviye analitik tool'lari."""
    from src.tools.sales.memory_tools import get_sales_memory

    return [
        # Outreach kontrolu
        outreach_pause,
        outreach_resume,
        # Auto-reply kontrolu (yeni — Faz 1)
        auto_reply_pause,
        auto_reply_resume,
        # Lead yazma (yeni)
        assign_lead,
        update_lead_stage,
        add_lead_note,
        # Hafiza (yapilandirilmis — structured memory_tools)
        get_sales_memory,
        # Ust seviye analitik
        pipeline_forecast,
        weekly_kpi,
    ]


__all__ = [
    "outreach_pause",
    "outreach_resume",
    "auto_reply_pause",
    "auto_reply_resume",
    "assign_lead",
    "update_lead_stage",
    "add_lead_note",
    "pipeline_forecast",
    "weekly_kpi",
    "get_management_tools",
    "VALID_LEAD_STAGES",
    "DEAL_STAGE_WEIGHTS",
    "DEFAULT_FIRSATLAR_TABLE_ID",
    # Impls for direct testing
    "_outreach_pause_impl",
    "_outreach_resume_impl",
    "_auto_reply_pause_impl",
    "_auto_reply_resume_impl",
    "_assign_lead_impl",
    "_update_lead_stage_impl",
    "_add_lead_note_impl",
    "_pipeline_forecast_impl",
    "_weekly_kpi_impl",
    "_week_start_utc",
]
