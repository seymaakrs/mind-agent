"""Read-only sales query tools.

These tools answer Şeyma's natural-language questions in mind-id's chat:
- "Kaç sıcak lead var?"
- "Bu hafta toplam pipeline kaç TL?"
- "Hangi kanal en düşük CAC üretiyor?"
- "Bugün hangi otonom kararlar alındı?"

All tools are READ-ONLY. None of them mutates the CRM. This is by design —
the query agent must never write so it can be safely exposed to humans.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client


# ---------------------------------------------------------------------------
# Hot leads
# ---------------------------------------------------------------------------


@function_tool
async def get_hot_leads_count() -> dict[str, Any]:
    """Skor 8 ve üzeri (sıcak) lead sayısını döndürür.

    Returns:
        ``{"success": True, "count": int}`` veya hata dict'i.
    """
    try:
        client = get_nocodb_client()
        # NocoDB v2 doesn't expose a cheap count; we list with high limit.
        rows = await client.query_records(
            client.config.leads_table_id,
            where="(lead_score,gte,8)",
            limit=1000,
        )
        return {"success": True, "count": len(rows)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def get_hot_leads(limit: int = 10) -> dict[str, Any]:
    """Sıcak (skor>=8) lead'leri en yeniden eskiye sıralı döndürür.

    Args:
        limit: Maksimum kayıt sayısı (1-50).
    """
    try:
        client = get_nocodb_client()
        rows = await client.query_records(
            client.config.leads_table_id,
            where="(lead_score,gte,8)",
            sort="-CreatedAt",
            limit=max(1, min(50, limit)),
        )
        return {"success": True, "count": len(rows), "data": rows}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def get_total_leads_count() -> dict[str, Any]:
    """Toplam lead sayısını döndürür."""
    try:
        client = get_nocodb_client()
        rows = await client.query_records(
            client.config.leads_table_id,
            limit=1000,
        )
        return {"success": True, "count": len(rows)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Pipeline & economics
# ---------------------------------------------------------------------------


@function_tool
async def get_pipeline_value() -> dict[str, Any]:
    """Açık pipeline değeri (TL) — closed/lost olmayan lead'lerin
    ``expected_revenue_try`` toplamı.
    """
    try:
        client = get_nocodb_client()
        rows = await client.query_records(
            client.config.leads_table_id,
            where="(lead_status,nin,closed,lost)",
            limit=1000,
        )
        total = 0.0
        by_status: dict[str, float] = defaultdict(float)
        for row in rows:
            try:
                val = float(row.get("expected_revenue_try") or 0)
            except (TypeError, ValueError):
                val = 0.0
            total += val
            by_status[str(row.get("lead_status", "unknown"))] += val
        return {
            "success": True,
            "pipeline_value_try": round(total, 2),
            "by_status": {k: round(v, 2) for k, v in by_status.items()},
            "lead_count": len(rows),
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def get_cac_by_channel() -> dict[str, Any]:
    """Kanal bazında ortalama CAC (Customer Acquisition Cost).

    `cac_attributed_try` alanı dolu olan (yani satış kapanmış) lead'lerden
    kanal bazında ortalama hesaplar.
    """
    try:
        client = get_nocodb_client()
        rows = await client.query_records(
            client.config.leads_table_id,
            where="(lead_status,eq,closed)",
            limit=1000,
        )
        sums: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            cac = row.get("cac_attributed_try")
            try:
                cac_val = float(cac) if cac is not None else None
            except (TypeError, ValueError):
                cac_val = None
            if cac_val is None:
                continue
            channel = str(row.get("source", "unknown"))
            sums[channel].append(cac_val)

        result: dict[str, dict[str, float]] = {}
        for channel, vals in sums.items():
            if not vals:
                continue
            result[channel] = {
                "avg_cac_try": round(sum(vals) / len(vals), 2),
                "sample_size": len(vals),
                "min_cac_try": round(min(vals), 2),
                "max_cac_try": round(max(vals), 2),
            }
        return {"success": True, "by_channel": result, "closed_lead_count": len(rows)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Today's funnel
# ---------------------------------------------------------------------------


@function_tool
async def get_today_funnel() -> dict[str, Any]:
    """Bugünkü huni: yeni lead, sıcaklaşan lead, kapanan satış sayıları.

    Bugün = UTC bugün (NocoDB CreatedAt UTC).
    """
    try:
        client = get_nocodb_client()
        today_str = datetime.now(timezone.utc).date().isoformat()  # YYYY-MM-DD
        # NocoDB filter: created today
        where = f"(CreatedAt,gte,{today_str})"
        rows = await client.query_records(
            client.config.leads_table_id,
            where=where,
            limit=1000,
        )
        funnel: dict[str, int] = defaultdict(int)
        funnel["new_leads"] = len(rows)
        for r in rows:
            status = str(r.get("lead_status") or "")
            if status == "hot":
                funnel["hot_leads"] += 1
            if status == "warm":
                funnel["warm_leads"] += 1
            if status == "closed":
                funnel["closed_leads"] += 1
            if status == "lost":
                funnel["lost_leads"] += 1
        return {
            "success": True,
            "date": today_str,
            "funnel": dict(funnel),
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Decisions log
# ---------------------------------------------------------------------------


@function_tool
async def get_recent_decisions(limit: int = 10) -> dict[str, Any]:
    """Son otonom kararları döndürür (decisions_log tablosu).

    CAIDO denetimi ve "bugün ne kararlar aldı?" sorusu için.
    """
    try:
        client = get_nocodb_client()
        if not client.config.decisions_log_table_id:
            return {
                "success": False,
                "error": "decisions_log table not configured",
                "error_code": "NOT_FOUND",
                "retryable": False,
            }
        rows = await client.query_records(
            client.config.decisions_log_table_id,
            sort="-timestamp",
            limit=max(1, min(50, limit)),
        )
        return {"success": True, "count": len(rows), "data": rows}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Agent health
# ---------------------------------------------------------------------------


@function_tool
async def get_agent_health_summary() -> dict[str, Any]:
    """Tüm agent'ların sağlık durumu (`agent_health` tablosu).

    UI'ın "yeşil/sarı/kırmızı" gösterimi için.
    """
    try:
        client = get_nocodb_client()
        if not client.config.agent_health_table_id:
            return {
                "success": False,
                "error": "agent_health table not configured",
                "error_code": "NOT_FOUND",
                "retryable": False,
            }
        rows = await client.query_records(
            client.config.agent_health_table_id,
            limit=100,
        )
        # Group by status
        summary: dict[str, int] = defaultdict(int)
        for r in rows:
            summary[str(r.get("status") or "unknown")] += 1
        return {
            "success": True,
            "summary": dict(summary),
            "agents": rows,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


__all__ = [
    "get_hot_leads_count",
    "get_hot_leads",
    "get_total_leads_count",
    "get_pipeline_value",
    "get_cac_by_channel",
    "get_today_funnel",
    "get_recent_decisions",
    "get_agent_health_summary",
]
