"""Read-only sales reporting tools for the Sales Analyst agent.

These tools query NocoDB ('Leadler' + 'Etkilesimler') and return structured
dicts with a `summary_tr` field plus the raw `data` payload, so the agent
can either narrate or hand the structured payload to the portal renderer.

All tools are READ-ONLY — they never write to the CRM, so they can never
corrupt Beyza's live schema or interfere with n8n workflows.

Schema reference: customer_agent/docs/NOCODB-SCHEMA-V2.md (v2.1)
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from agents import function_tool

from src.app.config import get_settings
from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 10
MAX_LIMIT = 500

FUNNEL_STAGES = [
    "Yeni",
    "Soguk",
    "Ilik",
    "Sicak",
    "Teklif",
    "Sozlesme",
    "Kazanildi",
    "Kayip",
    "Arsiv",
]

KNOWN_CHANNELS = [
    "Meta Ads",
    "LinkedIn",
    "Clay",
    "IG DM",
    "TikTok DM",
    "Referans",
    "Manuel",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _leads_table() -> str | None:
    return get_settings().nocodb_leads_table_id


def _messages_table() -> str | None:
    return get_settings().nocodb_messages_table_id


def _missing_table_error(name: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": f"NocoDB {name} table id is not configured.",
        "error_code": "INVALID_INPUT",
        "service": "nocodb",
        "retryable": False,
        "user_message_tr": "CRM tablo ayarlari eksik, raporlama yapilamadi.",
    }


def _clamp_limit(limit: int | None) -> int:
    if not limit or limit <= 0:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def _build_where(
    asama: str | None = None,
    kaynak: str | None = None,
    atanan_kisi: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_field: str = "CreatedAt",
) -> str | None:
    """Build NocoDB v2 `where` query string from common filters.

    Format: '(field,op,value)~and(field,op,value)'
    """
    parts: list[str] = []
    if asama:
        parts.append(f"({asama_field()},eq,{asama})")
    if kaynak:
        parts.append(f"(kaynak,eq,{kaynak})")
    if atanan_kisi:
        parts.append(f"(atanan_kisi,eq,{atanan_kisi})")
    if date_from:
        parts.append(f"({date_field},ge,{date_from})")
    if date_to:
        parts.append(f"({date_field},le,{date_to})")
    if not parts:
        return None
    return "~and".join(parts)


def asama_field() -> str:
    """The Leadler stage column name (kept as a function so the rare schema
    rename happens in one spot)."""
    return "asama"


def _fetch_all(
    table_id: str,
    *,
    where: str | None = None,
    sort: str | None = None,
    page_size: int = 100,
    hard_cap: int = 2000,
) -> list[dict[str, Any]]:
    """Page through NocoDB until exhausted (or hard cap)."""
    client = get_nocodb_client()
    out: list[dict[str, Any]] = []
    offset = 0
    while len(out) < hard_cap:
        result = client.list_records(
            table_id, where=where, limit=page_size, sort=sort
        )
        rows = result.get("list", []) if isinstance(result, dict) else []
        if not rows:
            break
        out.extend(rows)
        page_info = (
            result.get("pageInfo", {}) if isinstance(result, dict) else {}
        )
        is_last = page_info.get("isLastPage")
        if is_last is True or len(rows) < page_size:
            break
        offset += page_size
    return out[:hard_cap]


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@function_tool(
    name_override="count_leads",
    description_override=(
        "Count leads in NocoDB Leadler with optional filters. "
        "Filters (all optional, all eq-match): "
        "asama (Yeni|Soguk|Ilik|Sicak|Teklif|Sozlesme|Kazanildi|Kayip|Arsiv), "
        "kaynak (Meta Ads|LinkedIn|Clay|IG DM|TikTok DM|Referans|Manuel), "
        "atanan_kisi (e.g. 'Seyma'), "
        "date_from / date_to (ISO date YYYY-MM-DD; filters Leadler.CreatedAt). "
        "Returns {count, filters, summary_tr}."
    ),
    strict_mode=False,
)
async def count_leads(
    asama: str | None = None,
    kaynak: str | None = None,
    atanan_kisi: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        where = _build_where(asama, kaynak, atanan_kisi, date_from, date_to)
        rows = _fetch_all(table_id, where=where)
        count = len(rows)
        filters = {
            "asama": asama,
            "kaynak": kaynak,
            "atanan_kisi": atanan_kisi,
            "date_from": date_from,
            "date_to": date_to,
        }
        bits = [f"{k}={v}" for k, v in filters.items() if v]
        filter_text = ", ".join(bits) if bits else "tum lead'ler"
        return {
            "success": True,
            "type": "count",
            "count": count,
            "filters": filters,
            "summary_tr": f"{filter_text} icin toplam {count} lead bulundu.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="list_leads",
    description_override=(
        "List leads from Leadler (read-only). Filters: asama, kaynak, atanan_kisi. "
        "sort: NocoDB sort string, e.g. '-lead_skoru' (DESC) or 'CreatedAt'. "
        "limit: default 10, max 500. "
        "Returns {data: [...], count, summary_tr}. "
        "Use this for 'son N lead', 'en yuksek skorlu', 'X kanalindaki lead'ler' tarzi sorular."
    ),
    strict_mode=False,
)
async def list_leads(
    asama: str | None = None,
    kaynak: str | None = None,
    atanan_kisi: str | None = None,
    sort: str | None = "-CreatedAt",
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        where = _build_where(asama, kaynak, atanan_kisi)
        client = get_nocodb_client()
        result = client.list_records(
            table_id, where=where, limit=_clamp_limit(limit), sort=sort
        )
        rows = result.get("list", []) if isinstance(result, dict) else []
        slim = [
            {
                "Id": r.get("Id"),
                "ad_soyad": r.get("ad_soyad"),
                "sirket_adi": r.get("sirket_adi"),
                "kaynak": r.get("kaynak"),
                "asama": r.get("asama"),
                "lead_skoru": r.get("lead_skoru"),
                "atanan_kisi": r.get("atanan_kisi"),
                "telefon": r.get("telefon"),
                "email": r.get("email"),
                "konum": r.get("konum"),
                "CreatedAt": r.get("CreatedAt"),
            }
            for r in rows
        ]
        return {
            "success": True,
            "type": "list",
            "schema": "leads",
            "count": len(slim),
            "data": slim,
            "summary_tr": f"{len(slim)} lead listelendi.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="lead_funnel",
    description_override=(
        "Funnel breakdown: count of leads per asama (Yeni->...->Kazanildi). "
        "Optional date_from / date_to (ISO YYYY-MM-DD) filter on CreatedAt. "
        "Returns {data: [{asama, count}...], total, summary_tr}."
    ),
    strict_mode=False,
)
async def lead_funnel(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        where = _build_where(date_from=date_from, date_to=date_to)
        rows = _fetch_all(table_id, where=where)
        counter: Counter[str] = Counter()
        for r in rows:
            stage = r.get("asama") or "Yeni"
            counter[stage] += 1
        # Ordered by canonical funnel stages first, then anything else
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for stage in FUNNEL_STAGES:
            ordered.append({"asama": stage, "count": counter.get(stage, 0)})
            seen.add(stage)
        for stage, c in counter.items():
            if stage not in seen:
                ordered.append({"asama": stage, "count": c})
        total = sum(counter.values())
        sicak = counter.get("Sicak", 0)
        kazanildi = counter.get("Kazanildi", 0)
        return {
            "success": True,
            "type": "funnel",
            "schema": "funnel",
            "data": ordered,
            "total": total,
            "summary_tr": (
                f"Toplam {total} lead; {sicak} Sicak, {kazanildi} Kazanildi."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="channel_breakdown",
    description_override=(
        "Per-channel (kaynak) breakdown of leads: count + average lead_skoru. "
        "Optional date_from / date_to (ISO YYYY-MM-DD). "
        "Returns {data: [{kaynak, count, avg_skor}...], total, summary_tr}. "
        "Use for 'hangi kanal en cok dondurdu', 'kaynak dagilimi' tarzi sorular."
    ),
    strict_mode=False,
)
async def channel_breakdown(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        where = _build_where(date_from=date_from, date_to=date_to)
        rows = _fetch_all(table_id, where=where)
        agg: dict[str, dict[str, Any]] = {}
        for r in rows:
            ch = r.get("kaynak") or "Bilinmeyen"
            bucket = agg.setdefault(ch, {"count": 0, "skor_total": 0, "skor_n": 0})
            bucket["count"] += 1
            skor = r.get("lead_skoru")
            if isinstance(skor, (int, float)):
                bucket["skor_total"] += skor
                bucket["skor_n"] += 1
        data: list[dict[str, Any]] = []
        for ch, b in agg.items():
            avg = round(b["skor_total"] / b["skor_n"], 1) if b["skor_n"] else None
            data.append({"kaynak": ch, "count": b["count"], "avg_skor": avg})
        data.sort(key=lambda x: x["count"], reverse=True)
        total = sum(b["count"] for b in agg.values())
        top = data[0]["kaynak"] if data else "-"
        return {
            "success": True,
            "type": "channel",
            "schema": "channel",
            "data": data,
            "total": total,
            "summary_tr": (
                f"Toplam {total} lead; en cok '{top}' kanalindan."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="stale_leads",
    description_override=(
        "Find leads stuck in a stage longer than `days` (based on Leadler.UpdatedAt "
        "if present, else CreatedAt). Default asama='Sicak', days=3. "
        "Returns {data: [{Id, ad_soyad, asama, son_guncelleme, gun}...], count, summary_tr}."
    ),
    strict_mode=False,
)
async def stale_leads(
    asama: str = "Sicak",
    days: int = 3,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        where = _build_where(asama=asama)
        rows = _fetch_all(table_id, where=where)
        now = _now_utc()
        threshold = timedelta(days=max(1, days))
        stale: list[dict[str, Any]] = []
        for r in rows:
            ts = _parse_dt(r.get("UpdatedAt")) or _parse_dt(r.get("CreatedAt"))
            if not ts:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = now - ts
            if age >= threshold:
                stale.append(
                    {
                        "Id": r.get("Id"),
                        "ad_soyad": r.get("ad_soyad"),
                        "sirket_adi": r.get("sirket_adi"),
                        "asama": r.get("asama"),
                        "son_guncelleme": ts.isoformat(),
                        "gun": age.days,
                        "atanan_kisi": r.get("atanan_kisi"),
                    }
                )
        stale.sort(key=lambda x: x["gun"], reverse=True)
        clipped = stale[: _clamp_limit(limit)]
        return {
            "success": True,
            "type": "list",
            "schema": "stale",
            "data": clipped,
            "count": len(stale),
            "summary_tr": (
                f"{len(stale)} lead {asama} asamasinda {days}+ gundur takili."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="lead_timeline",
    description_override=(
        "All Etkilesimler rows for a lead (matched on lead_adi string match). "
        "Sorted newest first. limit default 20, max 500. "
        "Returns {data: [{tarih, kanal, yon, tur, mesaj_icerigi, sonuc, agent}...], count, summary_tr}."
    ),
    strict_mode=False,
)
async def lead_timeline(
    ad_soyad: str,
    limit: int = 20,
) -> dict[str, Any]:
    table_id = _messages_table()
    if not table_id:
        return _missing_table_error("messages")
    try:
        where = f"(lead_adi,eq,{ad_soyad})"
        client = get_nocodb_client()
        result = client.list_records(
            table_id, where=where, limit=_clamp_limit(limit), sort="-tarih"
        )
        rows = result.get("list", []) if isinstance(result, dict) else []
        data = [
            {
                "tarih": r.get("tarih"),
                "kanal": r.get("kanal"),
                "yon": r.get("yon"),
                "tur": r.get("tur"),
                "mesaj_icerigi": r.get("mesaj_icerigi"),
                "sonuc": r.get("sonuc"),
                "agent": r.get("agent"),
            }
            for r in rows
        ]
        return {
            "success": True,
            "type": "timeline",
            "schema": "timeline",
            "lead": ad_soyad,
            "data": data,
            "count": len(data),
            "summary_tr": f"{ad_soyad} icin {len(data)} etkilesim bulundu.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="daily_digest",
    description_override=(
        "Daily snapshot for a given ISO date (default: today UTC). "
        "Returns yeni_lead_count, sicak_count, kazanildi_count, "
        "seyma_assigned_count, top_channel, summary_tr."
    ),
    strict_mode=False,
)
async def daily_digest(date: str | None = None) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        target = date or _now_utc().date().isoformat()
        # day window
        day_from = f"{target}T00:00:00Z"
        day_to = f"{target}T23:59:59Z"
        client = get_nocodb_client()

        # New today
        new_where = _build_where(date_from=day_from, date_to=day_to)
        new_rows = _fetch_all(table_id, where=new_where)
        # Currently Sicak
        sicak = client.list_records(
            table_id, where="(asama,eq,Sicak)", limit=1
        )
        sicak_total = (
            sicak.get("pageInfo", {}).get("totalRows")
            if isinstance(sicak, dict)
            else None
        )
        if sicak_total is None:
            sicak_total = len(_fetch_all(table_id, where="(asama,eq,Sicak)"))
        # Kazanildi today
        won_where = (
            f"(asama,eq,Kazanildi)~and(UpdatedAt,ge,{day_from})~and(UpdatedAt,le,{day_to})"
        )
        won_rows = _fetch_all(table_id, where=won_where)
        # Seyma assigned (waiting)
        seyma_rows = _fetch_all(
            table_id, where="(atanan_kisi,eq,Seyma)~and(asama,neq,Kazanildi)"
        )

        # Top channel today
        ch_counter: Counter[str] = Counter()
        for r in new_rows:
            ch_counter[r.get("kaynak") or "Bilinmeyen"] += 1
        top_channel = ch_counter.most_common(1)[0][0] if ch_counter else "-"

        return {
            "success": True,
            "type": "digest",
            "schema": "digest",
            "date": target,
            "data": {
                "yeni_lead_count": len(new_rows),
                "sicak_count": sicak_total,
                "kazanildi_count": len(won_rows),
                "seyma_bekleyen_count": len(seyma_rows),
                "top_channel": top_channel,
            },
            "summary_tr": (
                f"{target}: {len(new_rows)} yeni lead, {sicak_total} Sicak, "
                f"{len(won_rows)} Kazanildi, Seyma'da bekleyen {len(seyma_rows)}. "
                f"En aktif kanal: {top_channel}."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Tool group
# ---------------------------------------------------------------------------


def get_reporting_tools() -> list:
    """All read-only sales reporting tools for the Sales Analyst agent."""
    return [
        count_leads,
        list_leads,
        lead_funnel,
        channel_breakdown,
        stale_leads,
        lead_timeline,
        daily_digest,
    ]


__all__ = [
    "count_leads",
    "list_leads",
    "lead_funnel",
    "channel_breakdown",
    "stale_leads",
    "lead_timeline",
    "daily_digest",
    "get_reporting_tools",
]
