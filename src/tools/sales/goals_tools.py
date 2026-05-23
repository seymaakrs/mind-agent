"""Sales Manager aylik hedef + KPI takip modulu.

3 tool:
  1. set_monthly_goal       — aylik hedef belirle (Firestore)
  2. get_monthly_progress   — guncel ilerleme + on_track sinyali
  3. list_goals             — son N hedef + basari durumu

Firestore path: businesses/{business_id}/sales_goals/{YYYY-MM}
metric: 'sicak_lead' | 'yeni_lead' | 'kazanildi' | 'total_outreach'
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client
from src.tools.sales.reporting_tools import _count_leads_impl

log = logging.getLogger(__name__)


VALID_METRICS = {"sicak_lead", "yeni_lead", "kazanildi", "total_outreach"}
_MIN_YEAR = 2025
_MAX_YEAR = 2030
_MIN_TARGET = 1
_MAX_TARGET = 100000


def _goals_collection_path(business_id: str) -> str:
    return f"businesses/{business_id}/sales_goals"


def _goal_doc_id(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_bounds(year: int, month: int) -> tuple[str, str, int]:
    """Returns (month_start_iso, today_iso_or_month_end, days_in_month)."""
    days_total = calendar.monthrange(year, month)[1]
    start = date(year, month, 1).isoformat()
    today = date.today()
    if (today.year, today.month) == (year, month):
        end = today.isoformat()
    else:
        end = date(year, month, days_total).isoformat()
    return start, end, days_total


async def _count_for_metric(
    metric: str, year: int, month: int
) -> int:
    """metric tipine gore _count_leads_impl cagir."""
    start, end, _ = _month_bounds(year, month)
    if metric == "sicak_lead":
        res = await _count_leads_impl(asama="Sicak", date_from=start, date_to=end)
    elif metric == "yeni_lead":
        res = await _count_leads_impl(date_from=start, date_to=end)
    elif metric == "kazanildi":
        res = await _count_leads_impl(asama="Kazanildi", date_from=start, date_to=end)
    elif metric == "total_outreach":
        res = await _count_leads_impl()
    else:
        return 0
    if not res.get("success"):
        return 0
    return int(res.get("count") or 0)


# ---------------------------------------------------------------------------
# 1) set_monthly_goal
# ---------------------------------------------------------------------------


async def _set_monthly_goal_impl(
    business_id: str,
    year: int,
    month: int,
    metric: str,
    target_value: int,
    reason: str,
) -> dict[str, Any]:
    """Aylik hedef belirle. Firestore merge=True."""
    if not business_id:
        return {"success": False, "error": "business_id zorunlu."}
    if metric not in VALID_METRICS:
        return {
            "success": False,
            "error": f"Gecersiz metric. Gecerli: {sorted(VALID_METRICS)}",
        }
    if not isinstance(year, int) or year < _MIN_YEAR or year > _MAX_YEAR:
        return {
            "success": False,
            "error": f"year {_MIN_YEAR}-{_MAX_YEAR} arasi olmali.",
        }
    if not isinstance(month, int) or month < 1 or month > 12:
        return {"success": False, "error": "month 1-12 arasi olmali."}
    if not isinstance(target_value, int) or target_value < _MIN_TARGET or target_value > _MAX_TARGET:
        return {
            "success": False,
            "error": f"target_value {_MIN_TARGET}-{_MAX_TARGET} arasi int olmali.",
        }
    if not reason or len(reason.strip()) < 5:
        return {"success": False, "error": "Sebep en az 5 karakter olmali."}

    try:
        client = get_document_client(_goals_collection_path(business_id))
        now = _now_iso()
        data = {
            "metric": metric,
            "target_value": target_value,
            "year": year,
            "month": month,
            "reason": reason,
            "created_at": now,
            "updated_at": now,
        }
        client.set_document(_goal_doc_id(year, month), data, merge=True)
        return {
            "success": True,
            "data": {
                "business_id": business_id,
                "year": year,
                "month": month,
                "metric": metric,
                "target_value": target_value,
            },
            "summary_tr": (
                f"{year}-{month:02d} icin hedef belirlendi: "
                f"{metric}={target_value}. Sebep: {reason}"
            ),
        }
    except Exception as exc:
        log.error("set_monthly_goal failed: %s", exc)
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# 2) get_monthly_progress
# ---------------------------------------------------------------------------


async def _get_monthly_progress_impl(
    business_id: str,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """Aylik hedef ilerlemesi."""
    if not business_id:
        return {"success": False, "error": "business_id zorunlu."}
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    try:
        client = get_document_client(_goals_collection_path(business_id))
        doc = client.get_document(_goal_doc_id(year, month))
    except Exception as exc:
        log.error("get_monthly_progress read failed: %s", exc)
        return {"success": False, "error": str(exc)}

    if not doc:
        return {
            "success": True,
            "data": None,
            "summary_tr": "Bu ay icin hedef belirlenmedi.",
        }

    metric = doc.get("metric")
    target = int(doc.get("target_value") or 0)
    current = await _count_for_metric(metric, year, month)

    days_total = calendar.monthrange(year, month)[1]
    if (today.year, today.month) == (year, month):
        days_elapsed = today.day
    elif (year, month) < (today.year, today.month):
        days_elapsed = days_total
    else:
        days_elapsed = 0
    days_remaining = days_total - days_elapsed

    progress_pct = (current / target) * 100 if target > 0 else 0.0
    expected_pct = (days_elapsed / days_total) * 100 if days_total > 0 else 0.0
    on_track = progress_pct >= expected_pct

    if days_remaining <= 0:
        daily_rate_needed = 0.0
    else:
        daily_rate_needed = max(0, target - current) / max(1, days_remaining)

    status = "yolunda" if on_track else "geride"
    return {
        "success": True,
        "data": {
            "metric": metric,
            "target": target,
            "current": current,
            "progress_pct": round(progress_pct, 2),
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "daily_rate_needed": round(daily_rate_needed, 2),
            "on_track": on_track,
            "year": year,
            "month": month,
        },
        "summary_tr": (
            f"{year}-{month:02d} {metric}: {current}/{target} "
            f"(%{progress_pct:.1f}) — {status}. "
            f"Kalan {days_remaining} gun, gunluk gerekli: {daily_rate_needed:.1f}"
        ),
    }


# ---------------------------------------------------------------------------
# 3) list_goals
# ---------------------------------------------------------------------------


async def _list_goals_impl(
    business_id: str,
    limit: int = 12,
) -> dict[str, Any]:
    """Son N hedef + achieved hesaplanmis sekilde listele."""
    if not business_id:
        return {"success": False, "error": "business_id zorunlu."}
    if not isinstance(limit, int) or limit < 1:
        limit = 12

    try:
        client = get_document_client(_goals_collection_path(business_id))
        docs = client.list_documents(limit=limit)
    except Exception as exc:
        log.error("list_goals read failed: %s", exc)
        return {"success": False, "error": str(exc)}

    # Sort by (year, month) desc
    def _key(d: dict[str, Any]) -> tuple[int, int]:
        return (int(d.get("year") or 0), int(d.get("month") or 0))

    docs_sorted = sorted(docs, key=_key, reverse=True)[:limit]

    results: list[dict[str, Any]] = []
    for d in docs_sorted:
        year = int(d.get("year") or 0)
        month = int(d.get("month") or 0)
        metric = d.get("metric")
        target = int(d.get("target_value") or 0)
        if not metric or year == 0 or month == 0:
            continue
        achieved = await _count_for_metric(metric, year, month)
        results.append({
            "year": year,
            "month": month,
            "metric": metric,
            "target": target,
            "achieved": achieved,
            "success": achieved >= target,
        })

    return {
        "success": True,
        "data": results,
        "summary_tr": f"{len(results)} hedef listelendi.",
    }


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


set_monthly_goal = function_tool(
    name_override="set_monthly_goal",
    description_override=(
        "Aylik satis hedefi belirle (Firestore'a yazar). "
        "metric: sicak_lead | yeni_lead | kazanildi | total_outreach. "
        "REQUIRED: business_id, year (2025-2030), month (1-12), "
        "metric, target_value (1-100000 int), reason (>=5 char)."
    ),
    strict_mode=False,
)(_set_monthly_goal_impl)


get_monthly_progress = function_tool(
    name_override="get_monthly_progress",
    description_override=(
        "Aylik hedefin guncel ilerlemesini getirir. "
        "year/month verilmezse simdiki ay. "
        "Donus: target, current, progress_pct, days_elapsed/remaining, "
        "daily_rate_needed, on_track."
    ),
    strict_mode=False,
)(_get_monthly_progress_impl)


list_goals = function_tool(
    name_override="list_goals",
    description_override=(
        "Son N aylik hedefi listele (varsayilan 12). "
        "Her hedef icin achieved hesaplanir, success=achieved>=target."
    ),
    strict_mode=False,
)(_list_goals_impl)


def get_goal_tools() -> list:
    """Sales Manager'a verilecek 3 hedef/KPI takip tool'u."""
    return [
        set_monthly_goal,
        get_monthly_progress,
        list_goals,
    ]


__all__ = [
    "set_monthly_goal",
    "get_monthly_progress",
    "list_goals",
    "get_goal_tools",
    "VALID_METRICS",
    # impl exports for testing
    "_set_monthly_goal_impl",
    "_get_monthly_progress_impl",
    "_list_goals_impl",
    "_count_for_metric",
]
