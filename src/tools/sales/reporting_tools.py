"""Read-only sales reporting tools for the Sales Analyst agent.

These tools query NocoDB ('Leadler' + 'Etkilesimler') and return structured
dicts with a `summary_tr` field plus the raw `data` payload, so the agent
can either narrate or hand the structured payload to the portal renderer.

All tools are READ-ONLY — they never write to the CRM, so they can never
corrupt Beyza's live schema or interfere with n8n workflows.

Pattern: each tool has a pure-async `_impl` (testable directly) plus a
`function_tool`-wrapped public name registered with the agent SDK.

Schema reference: customer_agent/docs/NOCODB-SCHEMA-V2.md (v2.1)
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from agents import function_tool

from src.app.config import get_settings
from src.infra.errors import classify_error
from src.infra.nocodb_client import (
    days_ago_filter_clause,
    get_nocodb_client,
    today_filter_clause,
)


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


def asama_field() -> str:
    """The Leadler stage column name (kept as a function so the rare schema
    rename happens in one spot)."""
    return "asama"


def _norm_date(value: str | None) -> str | None:
    """Coerce an incoming date to NocoDB-friendly YYYY-MM-DD, else None.

    Accepts 'YYYY-MM-DD' or any ISO datetime ('YYYY-MM-DDThh:mm:ss...').
    Unparseable values (e.g. free text like 'bu ay') return None so the
    filter is skipped instead of poisoning the query (was -> NocoDB 400).
    """
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        if len(v) >= 10 and v[4] == "-" and v[7] == "-" and v[:10].replace("-", "").isdigit():
            return v[:10]
        return None


def _build_where(
    asama: str | None = None,
    kaynak: str | None = None,
    atanan_kisi: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_field: str = "CreatedAt",
) -> str | None:
    """Build NocoDB v2 `where` query string from common filters.

    Format: '(field,op,value)~and(field,op,value)'. Date filters use the
    NocoDB v2 `exactDate` operator — plain ISO values are rejected (400/422).
    """
    parts: list[str] = []
    if asama:
        parts.append(f"({asama_field()},eq,{asama})")
    if kaynak:
        parts.append(f"(kaynak,eq,{kaynak})")
    if atanan_kisi:
        parts.append(f"(atanan_kisi,eq,{atanan_kisi})")
    df = _norm_date(date_from)
    if df:
        parts.append(f"({date_field},ge,exactDate,{df})")
    dt = _norm_date(date_to)
    if dt:
        parts.append(f"({date_field},le,exactDate,{dt})")
    if not parts:
        return None
    return "~and".join(parts)


def _fetch_all(
    table_id: str,
    *,
    where: str | None = None,
    sort: str | None = None,
    page_size: int = 100,
    hard_cap: int = 20000,
) -> list[dict[str, Any]]:
    """Page through NocoDB via `offset` until exhausted (or safety cap).

    The previous version never advanced an offset, so it re-fetched page 1
    forever and inflated to the cap (any >=100 result reported as 2000).
    """
    client = get_nocodb_client()
    out: list[dict[str, Any]] = []
    offset = 0
    while len(out) < hard_cap:
        result = client.list_records(
            table_id, where=where, limit=page_size, sort=sort, offset=offset
        )
        rows = result.get("list", []) if isinstance(result, dict) else []
        if not rows:
            break
        out.extend(rows)
        page_info = (
            result.get("pageInfo", {}) if isinstance(result, dict) else {}
        )
        if page_info.get("isLastPage") is True or len(rows) < page_size:
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
# Tool implementations (pure async — testable directly)
# ---------------------------------------------------------------------------


async def _count_leads_impl(
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
        # True total via NocoDB /records/count — NOT len(_fetch_all): _fetch_all
        # re-fetches page 1 (no offset) and caps at 2000, so any >=100 result
        # always reported exactly 2000.
        count = get_nocodb_client().count_records(table_id, where=where)
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


async def _list_leads_impl(
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


async def _lead_funnel_impl(
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


async def _channel_breakdown_impl(
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
            "summary_tr": f"Toplam {total} lead; en cok '{top}' kanalindan.",
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _stale_leads_impl(
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


async def _lead_timeline_impl(
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


async def _daily_digest_impl(date: str | None = None) -> dict[str, Any]:
    table_id = _leads_table()
    if not table_id:
        return _missing_table_error("leads")
    try:
        target = date or _now_utc().date().isoformat()
        day_from = f"{target}T00:00:00Z"
        day_to = f"{target}T23:59:59Z"
        client = get_nocodb_client()

        new_where = _build_where(date_from=day_from, date_to=day_to)
        new_rows = _fetch_all(table_id, where=new_where)

        sicak = client.list_records(table_id, where="(asama,eq,Sicak)", limit=1)
        sicak_total = (
            sicak.get("pageInfo", {}).get("totalRows")
            if isinstance(sicak, dict)
            else None
        )
        if sicak_total is None:
            sicak_total = len(_fetch_all(table_id, where="(asama,eq,Sicak)"))

        won_where = (
            f"(asama,eq,Kazanildi)~and(UpdatedAt,ge,{day_from})~and(UpdatedAt,le,{day_to})"
        )
        won_rows = _fetch_all(table_id, where=won_where)

        seyma_rows = _fetch_all(
            table_id, where="(atanan_kisi,eq,Seyma)~and(asama,neq,Kazanildi)"
        )

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
# Adim 8 (C): Runtime status tools — Outreach + Auto-reply worker'lar
# canliyken MindBot'un "su an ne durumdayiz?" sorulari icin.
# ---------------------------------------------------------------------------


def _outreach_daily_limit() -> int:
    """Read from OUTREACH_DAILY_LIMIT env (default 240, matches OutreachConfig)."""
    try:
        return int(os.environ.get("OUTREACH_DAILY_LIMIT", "240"))
    except (TypeError, ValueError):
        return 240


def _settings_table() -> str | None:
    """Optional `system_settings` table for Guardian-controlled flags."""
    return os.environ.get("NOCODB_SETTINGS_TABLE_ID") or None


async def _outreach_status_impl() -> dict[str, Any]:
    """Outreach Robotu'nun anlik durumu: bugun atilan + son saat + kalan kapasite."""
    msgs_tbl = _messages_table()
    if not msgs_tbl:
        return _missing_table_error("messages")
    try:
        now = _now_utc()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        one_hour_ago = now - timedelta(hours=1)
        daily_limit = _outreach_daily_limit()

        # NocoDB v2 datetime filter sadece exactDate/daysAgo operatorlerini
        # kabul ediyor (saat hassasiyeti yok). Bugun gondericileri NocoDB'den
        # kaba al, "son 1 saat"'i Python tarafinda ince filter et.
        today_rows = _fetch_all(
            msgs_tbl,
            where=(
                f"(yon,eq,Giden)~and(agent,eq,Outreach Agent)"
                f"~and{today_filter_clause('tarih', now)}"
            ),
        )
        last_hour_rows = [
            r for r in today_rows
            if (_dt := _parse_dt(r.get("tarih"))) and _dt >= one_hour_ago
        ]
        sent_today = len(today_rows)
        sent_last_hour = len(last_hour_rows)
        remaining = max(0, daily_limit - sent_today)
        percent_used = round(100 * sent_today / daily_limit, 1) if daily_limit else 0.0

        return {
            "success": True,
            "sent_today": sent_today,
            "daily_limit": daily_limit,
            "remaining": remaining,
            "percent_used": percent_used,
            "sent_last_hour": sent_last_hour,
            "summary_tr": (
                f"Bugun {sent_today}/{daily_limit} mesaj atildi "
                f"(%{percent_used}). Son 1 saatte {sent_last_hour} mesaj. "
                f"Kalan kapasite: {remaining}."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _auto_reply_status_impl() -> dict[str, Any]:
    """Auto-reply Agent son 24 saatte: kac inbound geldi, kacina yanit gonderildi."""
    msgs_tbl = _messages_table()
    if not msgs_tbl:
        return _missing_table_error("messages")
    try:
        now = _now_utc()
        day_clause = days_ago_filter_clause("tarih", 1)
        inbound = _fetch_all(
            msgs_tbl, where=f"(yon,eq,Gelen)~and{day_clause}"
        )
        outgoing_auto = _fetch_all(
            msgs_tbl,
            where=(
                f"(yon,eq,Giden)~and(agent,eq,Auto-reply Agent)"
                f"~and{day_clause}"
            ),
        )
        pending = [r for r in inbound if not r.get("auto_reply_processed")]

        n_in = len(inbound)
        n_out = len(outgoing_auto)
        rate = round(100 * n_out / n_in, 1) if n_in else 0.0

        return {
            "success": True,
            "window_hours": 24,
            "inbound_count": n_in,
            "auto_replies_sent": n_out,
            "response_rate_pct": rate,
            "pending_unprocessed": len(pending),
            "summary_tr": (
                f"Son 24 saatte {n_in} otel cevap verdi, {n_out} otomatik "
                f"yanit gonderildi (%{rate}). Bekleyen: {len(pending)} "
                f"(genelde olumsuz/spam — sessiz birakildi)."
            ),
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


async def _outreach_health_impl() -> dict[str, Any]:
    """Outreach Robotu su an PAUSE durumunda mi?

    SINGLE SOURCE OF TRUTH: `get_guardian_status` Bekci'nin tum durumunu
    okur (level, metrics, pause flag). `outreach_health` artik onu
    sarmalar ve geri uyumlu (paused/active/reason) sekle map eder.
    Iki tool'un ayni flag'i bagimsiz okumasi tutarsizlik riski idi.
    """
    from src.tools.guardian_tools import _get_guardian_status_impl

    status = await _get_guardian_status_impl()

    if not status.get("success"):
        # Guardian env yok veya read hatasi → eski "aktif varsayilir" davranisi
        return {
            "success": True,
            "configured": status.get("configured", False),
            "active": True,
            "paused": False,
            "reason": None,
            "summary_tr": (
                "Outreach Robotu aktif. (Bekci Robot/system_settings henuz "
                "kurulmamis — manuel pause kontrolu yok.)"
            ),
        }

    paused = bool(status.get("outreach_paused"))
    reason = status.get("pause_reason") or None
    pause_ts = status.get("paused_at") or None
    return {
        "success": True,
        "configured": True,
        "active": not paused,
        "paused": paused,
        "reason": reason,
        "paused_at": pause_ts,
        "summary_tr": (
            f"Outreach Robotu DURDURULDU. Sebep: {reason or 'belirtilmemis'}."
            + (f" (Pause zamani: {pause_ts})" if pause_ts else "")
            if paused else
            "Outreach Robotu aktif, kampanya devam ediyor."
        ),
    }


# ---------------------------------------------------------------------------
# Tool registrations (function_tool wrappers — exposed to the SDK)
# ---------------------------------------------------------------------------


count_leads = function_tool(
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
)(_count_leads_impl)


list_leads = function_tool(
    name_override="list_leads",
    description_override=(
        "List leads from Leadler (read-only). Filters: asama, kaynak, atanan_kisi. "
        "sort: NocoDB sort string, e.g. '-lead_skoru' (DESC) or 'CreatedAt'. "
        "limit: default 10, max 500. "
        "Returns {data: [...], count, summary_tr}. "
        "Use this for 'son N lead', 'en yuksek skorlu', 'X kanalindaki lead'ler' tarzi sorular."
    ),
    strict_mode=False,
)(_list_leads_impl)


lead_funnel = function_tool(
    name_override="lead_funnel",
    description_override=(
        "Funnel breakdown: count of leads per asama (Yeni->...->Kazanildi). "
        "Optional date_from / date_to (ISO YYYY-MM-DD) filter on CreatedAt. "
        "Returns {data: [{asama, count}...], total, summary_tr}."
    ),
    strict_mode=False,
)(_lead_funnel_impl)


channel_breakdown = function_tool(
    name_override="channel_breakdown",
    description_override=(
        "Per-channel (kaynak) breakdown of leads: count + average lead_skoru. "
        "Optional date_from / date_to (ISO YYYY-MM-DD). "
        "Returns {data: [{kaynak, count, avg_skor}...], total, summary_tr}. "
        "Use for 'hangi kanal en cok dondurdu', 'kaynak dagilimi' tarzi sorular."
    ),
    strict_mode=False,
)(_channel_breakdown_impl)


stale_leads = function_tool(
    name_override="stale_leads",
    description_override=(
        "Find leads stuck in a stage longer than `days` (based on Leadler.UpdatedAt "
        "if present, else CreatedAt). Default asama='Sicak', days=3. "
        "Returns {data: [{Id, ad_soyad, asama, son_guncelleme, gun}...], count, summary_tr}."
    ),
    strict_mode=False,
)(_stale_leads_impl)


lead_timeline = function_tool(
    name_override="lead_timeline",
    description_override=(
        "All Etkilesimler rows for a lead (matched on lead_adi string match). "
        "Sorted newest first. limit default 20, max 500. "
        "Returns {data: [{tarih, kanal, yon, tur, mesaj_icerigi, sonuc, agent}...], count, summary_tr}."
    ),
    strict_mode=False,
)(_lead_timeline_impl)


daily_digest = function_tool(
    name_override="daily_digest",
    description_override=(
        "Daily snapshot for a given ISO date (default: today UTC). "
        "Returns yeni_lead_count, sicak_count, kazanildi_count, "
        "seyma_assigned_count, top_channel, summary_tr."
    ),
    strict_mode=False,
)(_daily_digest_impl)


# ---------------------------------------------------------------------------
# Tool group
# ---------------------------------------------------------------------------


outreach_status = function_tool(
    name_override="outreach_status",
    description_override=(
        "Outreach Robotu'nun ANLIK durumu: bugun atilan mesaj sayisi, "
        "gunluk limit (240 default), son 1 saatlik tempo, kalan kapasite. "
        "Argumansiz. 'Bugun kac mesaj atildi?', 'Outreach hizinda mi?', "
        "'Limit dolmus mu?' gibi sorular icin."
    ),
    strict_mode=False,
)(_outreach_status_impl)


auto_reply_status = function_tool(
    name_override="auto_reply_status",
    description_override=(
        "Auto-reply (Cevap Robotu) son 24 saat durumu: kac otel cevap "
        "verdi, kacina otomatik yanit gonderildi, response rate %, "
        "bekleyen (sessiz birakilmis — genelde olumsuz/spam) sayisi. "
        "Argumansiz. 'Bugun kac cevap geldi?', 'Auto-reply calisiyor mu?', "
        "'Reply rate ne?' gibi sorular icin."
    ),
    strict_mode=False,
)(_auto_reply_status_impl)


outreach_health = function_tool(
    name_override="outreach_health",
    description_override=(
        "Outreach Robotu su an aktif mi PAUSE durumunda mi? "
        "Bekci Robot (Guardian) kotu reply rate / spam / ban riski "
        "yakaladiginda outreach'i durdurur. Bu tool durumun + sebebini "
        "dondurur. Argumansiz. 'Kampanya neden durdu?', 'Outreach calisiyor mu?'"
    ),
    strict_mode=False,
)(_outreach_health_impl)


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
        outreach_status,
        auto_reply_status,
        outreach_health,
    ]


__all__ = [
    "count_leads",
    "list_leads",
    "lead_funnel",
    "channel_breakdown",
    "stale_leads",
    "lead_timeline",
    "daily_digest",
    "outreach_status",
    "auto_reply_status",
    "outreach_health",
    "get_reporting_tools",
    # Implementation functions exposed for direct testing
    "_count_leads_impl",
    "_list_leads_impl",
    "_lead_funnel_impl",
    "_channel_breakdown_impl",
    "_stale_leads_impl",
    "_lead_timeline_impl",
    "_daily_digest_impl",
    "_outreach_status_impl",
    "_auto_reply_status_impl",
    "_outreach_health_impl",
]
