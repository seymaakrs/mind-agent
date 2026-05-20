"""Follow-up Agent main loop — Cloud Run job entry-point.

    python -m src.agents.followup.runner

Genel akis:
1. Guardian outreach_paused mi? Evet -> uyu (kapali dongu; outreach'la
   ayni bayrak, follow-up ayri flag actirmaz).
2. Business hours + daily limit kontrolu.
3. find_followup_targets: cevapsiz, 3+ gunluk soguk leadler.
4. send_one: Zernio takip template'ini at, lead.notlar'a 'Takip
   gonderildi' isareti koy (idempotency), asama 'Takipte' yap,
   Etkilesimler 'Takip' satiri ekle, contact tag'a 'takip_atildi'.
5. Jitter + batch break.

DRY_RUN: tum yazma/gonderim atlanir, sadece sinflandirma + log.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from src.agents.followup.policy import FollowupConfig, FollowupPolicy
from src.agents.followup.targeting import (
    _FOLLOWUP_MARKER,
    count_sent_today,
    find_followup_targets,
)
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client
from src.infra.zernio import get_zernio_client


log = logging.getLogger("followup")

_PAUSE_NO_TARGET_SEC = 600     # 10dk — takip listesi yavas dolar
_PAUSE_OFF_HOURS_SEC = 600
_PAUSE_DAILY_LIMIT_SEC = 1800
_PAUSE_ERROR_SEC = 60
_PAUSE_GUARDIAN_SEC = 300

_SEND_RETRIES = 2
_SEND_RETRY_DELAY_SEC = 30


def _is_outreach_paused() -> bool:
    """Guardian PAUSE bayragi (outreach ile ayni flag — sistem bozuksa hicbiri yazmaz)."""
    table_id = os.environ.get("NOCODB_SETTINGS_TABLE_ID")
    if not table_id:
        return False
    try:
        result = get_nocodb_client().list_records(table_id, limit=1)
        rows = result.get("list") or []
        if not rows:
            return False
        return bool(rows[0].get("outreach_paused"))
    except Exception as exc:
        log.warning("followup: pause-flag check failed: %s — assuming active", exc)
        return False


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
                    "followup: send_template failed (attempt %d/%d): %s — retry in %ds",
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
    config: FollowupConfig,
    leads_table: str,
    messages_table: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    phone = (lead.get("telefon") or "").strip()
    name = lead.get("ad_soyad") or lead.get("sirket_adi") or "Lead"
    lead_id = lead.get("Id")

    if dry_run:
        log.info("[DRY_RUN] would send followup template to %s (%s) lead_id=%s", name, phone, lead_id)
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

    # Lead: asama Takipte + notlar'a 'Takip gonderildi' isareti (idempotency)
    nocodb.update_record(
        leads_table,
        int(lead_id),
        {
            "asama": "Takipte",
            "son_temas": timestamp,
            "notlar": (lead.get("notlar") or "")
            + f"\n[{timestamp}] {_FOLLOWUP_MARKER} (template={config.template_name})",
        },
    )

    if messages_table:
        platform_message_id = (
            send_result.get("messageId")
            or send_result.get("message_id")
            or f"followup_{lead_id}_{int(datetime.now(timezone.utc).timestamp())}"
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
                    "tur": "Takip",
                    "mesaj_icerigi": f"Template: {config.template_name} variables=[{name}]",
                    "external_message_id": platform_message_id,
                    "agent": "Followup Agent",
                    "otomatik_mi": True,
                },
            )
        except Exception as exc:
            log.warning("followup: Etkilesimler log failed (lead_id=%s): %s", lead_id, exc)

    await _tag_zernio_contact(zernio, phone, to_add=["takip_atildi", "followup_v1"])

    log.info("followup: sent to %s (%s) lead_id=%s", name, phone, lead_id)
    return {"success": True, "lead_id": lead_id, "phone": phone, "raw": send_result}


async def _tag_zernio_contact(
    zernio: Any, phone: str, *, to_add: list[str]
) -> None:
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
            log.info("followup: zernio contact not found for phone=%s (tag skipped)", phone)
            return
        existing = list(match.get("tags") or [])
        merged = sorted(set(existing + to_add))
        await zernio.tag_contact(match["id"], merged)
    except Exception as exc:
        log.warning("followup: tag_contact failed phone=%s: %s", phone, exc)


async def loop(
    config: FollowupConfig | None = None, *, max_iterations: int | None = None
) -> None:
    config = config or FollowupConfig.from_env()
    policy = FollowupPolicy(config)
    settings = get_settings()
    leads_table = settings.nocodb_leads_table_id
    messages_table = settings.nocodb_messages_table_id
    dry_run = settings.dry_run

    if not leads_table:
        log.error("NOCODB_LEADS_TABLE_ID not configured — followup cannot run")
        return

    # Restart-safe daily counter: outreach ile ayni desen
    if messages_table and not dry_run:
        try:
            already = count_sent_today(get_nocodb_client(), messages_table)
            policy.sent_today = already
            log.info("Followup: recovered sent_today=%d from NocoDB", already)
        except Exception as exc:
            log.warning("Followup: count_sent_today failed (%s) — starting from 0", exc)

    log.info(
        "Followup starting: tz=%s hours=%d-%d daily_limit=%d days_since=%d sent_today=%d dry_run=%s template=%s",
        config.timezone,
        config.hour_start,
        config.hour_end,
        config.daily_limit,
        config.days_since_outreach,
        policy.sent_today,
        dry_run,
        config.template_name,
    )

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            if _is_outreach_paused():
                log.info("followup: PAUSED by Guardian, sleeping %ds", _PAUSE_GUARDIAN_SEC)
                await asyncio.sleep(_PAUSE_GUARDIAN_SEC)
                continue

            eligible, reason = policy.is_eligible()
            if not eligible:
                pause = (
                    _PAUSE_OFF_HOURS_SEC
                    if reason == "outside business hours"
                    else _PAUSE_DAILY_LIMIT_SEC
                )
                log.info("followup: not eligible (%s), sleeping %ds", reason, pause)
                await asyncio.sleep(pause)
                continue

            targets = find_followup_targets(
                get_nocodb_client(),
                leads_table,
                config.source_workflow_id,
                days_since_outreach=config.days_since_outreach,
            )
            if not targets:
                log.info("followup: no eligible targets, sleeping %ds", _PAUSE_NO_TARGET_SEC)
                await asyncio.sleep(_PAUSE_NO_TARGET_SEC)
                continue

            target = targets[0]  # en eski temas ilk (sort=son_temas asc)
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
                log.info("followup: batch break (%ds)", int(pause))
                await asyncio.sleep(pause)
            else:
                await asyncio.sleep(policy.next_delay_sec())
        except Exception as exc:
            log.exception("followup: loop iteration failed: %s", exc)
            await asyncio.sleep(_PAUSE_ERROR_SEC)


def _install_sigterm_handler() -> asyncio.Event:
    stop_event = asyncio.Event()

    def _stop(*_: object) -> None:
        log.info("followup: SIGTERM received, draining")
        stop_event.set()

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
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
