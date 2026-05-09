"""Outreach Agent main loop — Cloud Run job entry-point.

Long-running worker. Reads NocoDB Leadler for eligible cold-outreach
targets, sends a Meta-approved WhatsApp template via Zernio, logs the
attempt to Etkilesimler and flips the lead's ``asama`` to ``Soguk``.

DRY_RUN mode (``DRY_RUN=true``) skips Zernio API calls and logs only —
keeps NocoDB writes off too, so it is safe in staging.

Run:
    python -m src.agents.outreach.runner

Stop the loop with SIGTERM (Cloud Run job termination signal). One iteration
is wrapped in try/except so a transient NocoDB or Zernio hiccup pauses for
60 seconds rather than crash-looping the container.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from src.agents.outreach.policy import OutreachConfig, OutreachPolicy
from src.agents.outreach.targeting import pick_next_target
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client
from src.infra.zernio import get_zernio_client


log = logging.getLogger("outreach")


_PAUSE_NO_TARGET_SEC = 120
_PAUSE_OFF_HOURS_SEC = 300
_PAUSE_DAILY_LIMIT_SEC = 1800  # 30 min — re-check whether the day rolled over
_PAUSE_ERROR_SEC = 60


# ---------------------------------------------------------------------------
# Send pipeline (one lead)
# ---------------------------------------------------------------------------


async def send_one(
    *,
    lead: dict[str, Any],
    config: OutreachConfig,
    leads_table: str,
    messages_table: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Drive a single send + log + state transition.

    Returns a dict for diagnostics (used by tests + log lines).
    """
    phone = (lead.get("telefon") or "").strip()
    name = lead.get("ad_soyad") or lead.get("sirket_adi") or "Lead"
    lead_id = lead.get("Id")

    if dry_run:
        log.info("[DRY_RUN] would send template to %s (%s) lead_id=%s", name, phone, lead_id)
        return {"success": True, "dry_run": True, "phone": phone, "lead_id": lead_id}

    zernio = get_zernio_client()
    send_result = await zernio.send_template(
        phone=phone,
        template_name=config.template_name,
        variables=[name],
        language=config.template_language,
    )

    nocodb = get_nocodb_client()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Lead lifecycle: Yeni -> Soguk (gonderildi, yanit bekleniyor)
    nocodb.update_record(
        leads_table,
        int(lead_id),
        {
            "asama": "Soguk",
            "notlar": (lead.get("notlar") or "")
            + f"\n[{timestamp}] Cold outreach gonderildi (template={config.template_name})",
        },
    )

    if messages_table:
        message_text = f"Template: {config.template_name} variables=[{name}]"
        platform_message_id = (
            send_result.get("messageId")
            or send_result.get("message_id")
            or f"outreach_{lead_id}_{int(datetime.now(timezone.utc).timestamp())}"
        )
        try:
            nocodb.upsert_record(
                messages_table,
                "external_message_id",
                {
                    "lead_adi": name,
                    "tarih": timestamp,
                    "kanal": "WhatsApp",
                    "yon": "Giden",
                    "tur": "Ilk Mesaj",
                    "mesaj_icerigi": message_text,
                    "external_message_id": platform_message_id,
                    "agent": "Outreach Agent",
                    "otomatik_mi": True,
                },
            )
        except Exception as exc:
            log.warning("outreach: Etkilesimler log failed (lead_id=%s): %s", lead_id, exc)

    log.info("outreach: sent to %s (%s) lead_id=%s", name, phone, lead_id)
    return {"success": True, "lead_id": lead_id, "phone": phone, "raw": send_result}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def loop(config: OutreachConfig | None = None, *, max_iterations: int | None = None) -> None:
    """Outreach worker loop. ``max_iterations`` is for tests only (None = forever)."""
    config = config or OutreachConfig.from_env()
    policy = OutreachPolicy(config)
    settings = get_settings()
    leads_table = settings.nocodb_leads_table_id
    messages_table = settings.nocodb_messages_table_id
    dry_run = settings.dry_run

    if not leads_table:
        log.error("NOCODB_LEADS_TABLE_ID not configured — outreach cannot pick targets")
        return

    log.info(
        "Outreach starting: tz=%s hours=%d-%d daily_limit=%d dry_run=%s template=%s",
        config.timezone,
        config.hour_start,
        config.hour_end,
        config.daily_limit,
        dry_run,
        config.template_name,
    )

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            eligible, reason = policy.is_eligible()
            if not eligible:
                pause = (
                    _PAUSE_OFF_HOURS_SEC
                    if reason == "outside business hours"
                    else _PAUSE_DAILY_LIMIT_SEC
                )
                log.info("outreach: not eligible (%s), sleeping %ds", reason, pause)
                await asyncio.sleep(pause)
                continue

            target = pick_next_target(
                get_nocodb_client(), leads_table, config.source_workflow_id
            )
            if not target:
                log.info("outreach: no eligible targets, sleeping %ds", _PAUSE_NO_TARGET_SEC)
                await asyncio.sleep(_PAUSE_NO_TARGET_SEC)
                continue

            await send_one(
                lead=target,
                config=config,
                leads_table=leads_table,
                messages_table=messages_table,
                dry_run=dry_run,
            )
            policy.record_send()

            if policy.should_take_batch_break():
                pause = policy.batch_break_sec()
                log.info("outreach: batch break (%ds)", int(pause))
                await asyncio.sleep(pause)
            else:
                await asyncio.sleep(policy.next_delay_sec())
        except Exception as exc:
            log.exception("outreach: loop iteration failed: %s", exc)
            await asyncio.sleep(_PAUSE_ERROR_SEC)


def _install_sigterm_handler() -> asyncio.Event:
    stop_event = asyncio.Event()

    def _stop(*_: object) -> None:
        log.info("outreach: SIGTERM received, draining")
        stop_event.set()

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
        # Not on main thread (test runner) — skip
        pass
    return stop_event


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _install_sigterm_handler()
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
