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
from src.agents.outreach.targeting import count_sent_today, pick_next_target
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client
from src.infra.zernio import get_zernio_client


log = logging.getLogger("outreach")


_PAUSE_NO_TARGET_SEC = 120
_PAUSE_OFF_HOURS_SEC = 300
_PAUSE_DAILY_LIMIT_SEC = 1800  # 30 min — re-check whether the day rolled over
_PAUSE_ERROR_SEC = 60

# Mirror Seyma's otel_gonderim.py: 2 retries, 30sn between. Transient Zernio
# hiccups (502/timeout/rate-limit) should not lose a lead — without retry the
# whole worker would pause 60sn AND skip the lead on next iteration since
# asama already flipped to Soguk in some failure modes.
_SEND_RETRIES = 2
_SEND_RETRY_DELAY_SEC = 30


# ---------------------------------------------------------------------------
# Send pipeline (one lead)
# ---------------------------------------------------------------------------


async def _send_with_retry(
    zernio: Any,
    *,
    phone: str,
    template_name: str,
    variables: list[str],
    language: str,
    retries: int,
    retry_delay_sec: int,
) -> dict[str, Any]:
    """Call Zernio send_template with N retries on exception."""
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await zernio.send_template(
                phone=phone,
                template_name=template_name,
                variables=variables,
                language=language,
            )
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                log.warning(
                    "outreach: send_template failed (attempt %d/%d): %s — retry in %ds",
                    attempt + 1,
                    retries + 1,
                    exc,
                    retry_delay_sec,
                )
                await asyncio.sleep(retry_delay_sec)
    raise last_exc  # type: ignore[misc]


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
    send_result = await _send_with_retry(
        zernio,
        phone=phone,
        template_name=config.template_name,
        variables=[name],
        language=config.template_language,
        retries=_SEND_RETRIES,
        retry_delay_sec=_SEND_RETRY_DELAY_SEC,
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

    # Zernio contact tagging — Beyza's CRM segmentation lives here (her segment
    # filtreleri tag bazinda). Seyma's local script set 'hot_lead/yaniti_var';
    # outreach's role is set 'kontak_atildi' + workflow marker.
    await _tag_zernio_contact(
        zernio, phone, to_add=["kontak_atildi", "outreach_v1"]
    )

    log.info("outreach: sent to %s (%s) lead_id=%s", name, phone, lead_id)
    return {"success": True, "lead_id": lead_id, "phone": phone, "raw": send_result}


async def _tag_zernio_contact(
    zernio: Any, phone: str, *, to_add: list[str]
) -> None:
    """Best-effort: find contact by phone, merge tags into existing set.

    Zernio ``PATCH /contacts/{id}`` does FULL REPLACE of tags so we must
    fetch existing first and merge. Failure here doesn't roll back the
    message — it's downstream CRM segmentation, not message delivery.
    """
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return
    try:
        data = await zernio.list_contacts(limit=100)
        match = None
        for c in data.get("contacts") or []:
            c_digits = "".join(ch for ch in str(c.get("phone", "")) if ch.isdigit())
            if c_digits and c_digits == digits:
                match = c
                break
        if not match:
            log.info("outreach: zernio contact not found for phone=%s (tag skipped)", phone)
            return
        existing = list(match.get("tags") or [])
        merged = sorted(set(existing + to_add))
        await zernio.tag_contact(match["id"], merged)
    except Exception as exc:
        log.warning("outreach: tag_contact failed phone=%s: %s", phone, exc)


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

    # Restart-safe daily counter: rebuild from NocoDB so a Cloud Run job
    # restart at 14:00 doesn't reset us to zero and let us blast another
    # full daily_limit (would trigger WhatsApp ban). Best-effort: if NocoDB
    # is unreachable we start at zero and live with the risk.
    if messages_table and not dry_run:
        try:
            already = count_sent_today(get_nocodb_client(), messages_table)
            policy.sent_today = already
            log.info("Outreach: recovered sent_today=%d from NocoDB", already)
        except Exception as exc:
            log.warning("Outreach: count_sent_today failed (%s) — starting from 0", exc)

    log.info(
        "Outreach starting: tz=%s hours=%d-%d daily_limit=%d sent_today=%d dry_run=%s template=%s",
        config.timezone,
        config.hour_start,
        config.hour_end,
        config.daily_limit,
        policy.sent_today,
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
