"""Sicak lead acil aksiyon (triage) tool'lari.

Is kurali: 4 gundur dokunulmamis sicak lead = kaybedilen para.
Mudur o lead'leri en iyi satisciya devreder, oncelik=acil yapar.

Iki tool:
  - triage_stale_hot_leads: bul + (priority=acil + reassign) + audit
  - triage_report: SADECE okuma, hangi lead'ler triage adayi listele
"""
from __future__ import annotations

import logging
from typing import Any

from agents import function_tool

from src.tools.sales.manager_actions import (
    _lead_priority_set_impl,
    _lead_reassign_impl,
)
from src.tools.sales.reporting_tools import _stale_leads_impl

log = logging.getLogger(__name__)


def _validate(
    business_id: str,
    days_threshold: int,
    target_owner: str,
) -> dict[str, Any] | None:
    if not isinstance(business_id, str) or not business_id.strip():
        return {"success": False, "error": "business_id zorunlu (bos olamaz)."}
    if not isinstance(days_threshold, int) or isinstance(days_threshold, bool):
        return {"success": False, "error": "days_threshold int olmali."}
    if days_threshold < 1 or days_threshold > 30:
        return {
            "success": False,
            "error": "days_threshold 1-30 arasi olmali.",
        }
    if not isinstance(target_owner, str) or len(target_owner.strip()) < 2:
        return {
            "success": False,
            "error": "target_owner en az 2 karakter olmali.",
        }
    return None


async def _triage_stale_hot_leads_impl(
    business_id: str,
    days_threshold: int = 3,
    target_owner: str = "Beyza",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sicak ama N+ gundur dokunulmamis lead'leri devret + priority=acil yap."""
    err = _validate(business_id, days_threshold, target_owner)
    if err:
        return err

    stale_res = await _stale_leads_impl(asama="Sicak", days=days_threshold)
    if not stale_res.get("success"):
        return stale_res

    leads = stale_res.get("data") or []
    actions_log: list[dict[str, Any]] = []
    actioned = 0
    reassigned = 0
    skipped = 0

    for lead in leads:
        lead_id = lead.get("Id")
        lead_name = lead.get("ad_soyad") or f"lead#{lead_id}"
        current_owner = lead.get("atanan_kisi")

        if current_owner == target_owner:
            skipped += 1
            continue

        applied: list[str] = []
        if not dry_run:
            pr_res = await _lead_priority_set_impl(
                lead_id,
                "acil",
                reason=f"{days_threshold}+ gun stale, otomatik triage",
            )
            if pr_res.get("success"):
                applied.append("priority=acil")

            rs_res = await _lead_reassign_impl(
                lead_id,
                target_owner,
                reason="acil aksiyon, eski atanan musait degil",
            )
            if rs_res.get("success"):
                applied.append(f"reassign={target_owner}")
                reassigned += 1
            actioned += 1
        else:
            applied = ["priority=acil", f"reassign={target_owner}"]

        actions_log.append(
            {
                "lead_id": lead_id,
                "lead_name": lead_name,
                "actions": applied,
            }
        )

    found = len(leads)
    mode = "DRY-RUN" if dry_run else "UYGULANDI"
    summary_tr = (
        f"[{mode}] {found} stale sicak lead bulundu. "
        f"{actioned} lead'e aksiyon, {reassigned} tanesi {target_owner}'ya devredildi. "
        f"{skipped} lead zaten {target_owner}'da, atlandi."
    )

    return {
        "success": True,
        "data": {
            "found_count": found,
            "actioned_count": actioned,
            "reassigned_count": reassigned,
            "skipped_count": skipped,
            "dry_run": dry_run,
            "actions": actions_log,
        },
        "summary_tr": summary_tr,
    }


async def _triage_report_impl(
    business_id: str,
    days_threshold: int = 3,
) -> dict[str, Any]:
    """SADECE okuma — triage adayi sicak lead'leri listele, yazma yapma."""
    err = _validate(business_id, days_threshold, "Beyza")
    if err:
        return err

    stale_res = await _stale_leads_impl(asama="Sicak", days=days_threshold)
    if not stale_res.get("success"):
        return stale_res

    leads = stale_res.get("data") or []
    actions_log = [
        {
            "lead_id": lead.get("Id"),
            "lead_name": lead.get("ad_soyad") or f"lead#{lead.get('Id')}",
            "actions": [],
        }
        for lead in leads
    ]
    found = len(leads)
    summary_tr = (
        f"[RAPOR] {found} stale sicak lead var (>= {days_threshold} gun). "
        f"Yazma yapilmadi."
    )
    return {
        "success": True,
        "data": {
            "found_count": found,
            "actioned_count": 0,
            "reassigned_count": 0,
            "skipped_count": 0,
            "dry_run": True,
            "actions": actions_log,
        },
        "summary_tr": summary_tr,
    }


triage_stale_hot_leads = function_tool(
    name_override="triage_stale_hot_leads",
    description_override=(
        "Sicak ama N gundur dokunulmamis lead'leri toplu triage et: "
        "priority=acil + target_owner'a devret. "
        "REQUIRED: business_id. Optional: days_threshold (1-30, default 3), "
        "target_owner (default 'Beyza'), dry_run (default False)."
    ),
    strict_mode=False,
)(_triage_stale_hot_leads_impl)


triage_report = function_tool(
    name_override="triage_report",
    description_override=(
        "Triage adayi sicak lead'leri SADECE listele (okuma, yazma yok). "
        "REQUIRED: business_id. Optional: days_threshold (1-30, default 3)."
    ),
    strict_mode=False,
)(_triage_report_impl)


def get_triage_tools() -> list:
    return [triage_stale_hot_leads, triage_report]


__all__ = [
    "triage_stale_hot_leads",
    "triage_report",
    "get_triage_tools",
    "_triage_stale_hot_leads_impl",
    "_triage_report_impl",
]
