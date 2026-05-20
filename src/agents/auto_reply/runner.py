"""Auto-reply Agent main loop — Cloud Run job entry-point.

    python -m src.agents.auto_reply.runner

Polling-based (60sn). Each tick:
1. Query Etkilesimler for unprocessed inbound rows (oldest first, max age 60dk).
2. For each row: jitter 30-60sn, fetch lead konusma gecmisi, call
   ``responder.decide_reply``, optionally send via Zernio, log outgoing
   message, mark inbound row processed, flip lead.asama.
3. DRY_RUN gates Zernio + NocoDB writes (still classifies for shadow log).

Itiraz: olumlu/soru ile AYNI akis. Insan onayi YOK, n8n handoff YOK.
HAFIZA: lead bazli son 10 mesaj decide_reply'a anchor olarak verilir;
hata olursa bos history ile devam edilir (defansif).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from src.agents.auto_reply.policy import AutoReplyConfig
from src.agents.auto_reply.responder import AutoReplyDecision, decide_reply
from src.agents.auto_reply.targeting import fetch_recent_history, find_pending_inbounds
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client
from src.infra.zernio import get_zernio_client


log = logging.getLogger("auto_reply")

_PAUSE_ERROR_SEC = 60
_HISTORY_LIMIT = 10

_SENDABLE_INTENTS = {"olumlu", "soru", "itiraz"}


async def handle_one(
    *,
    inbound_row: dict[str, Any],
    config: AutoReplyConfig,
    leads_table: str,
    messages_table: str,
    dry_run: bool,
) -> dict[str, Any]:
    """End-to-end handling of a single inbound row."""
    row_id = inbound_row.get("Id")
    text = inbound_row.get("mesaj_icerigi") or ""
    lead_name = inbound_row.get("lead_adi") or ""

    if not text.strip():
        log.info("auto_reply: empty body row_id=%s skipped", row_id)
        if not dry_run:
            get_nocodb_client().update_record(
                messages_table, int(row_id), {"auto_reply_processed": True}
            )
        return {"row_id": row_id, "skipped": "empty"}

    # Konusma hafizasi (defansif — hata bos liste demek)
    history: list[dict[str, Any]] = []
    if lead_name:
        try:
            history = fetch_recent_history(
                get_nocodb_client(),
                messages_table,
                lead_name,
                limit=_HISTORY_LIMIT,
                exclude_row_id=int(row_id) if row_id is not None else None,
            )
        except Exception as exc:
            log.warning("auto_reply: history fetch failed row_id=%s: %s", row_id, exc)
            history = []

    decision: AutoReplyDecision = await decide_reply(
        text, config=config, conversation_history=history
    )
    log.info(
        "auto_reply: classify row_id=%s intent=%s conf=%.2f obj=%s history=%d will_reply=%s",
        row_id,
        decision.intent,
        decision.confidence,
        decision.objection_type,
        len(history),
        bool(decision.reply_text),
    )

    nocodb = get_nocodb_client()
    timestamp = datetime.now(timezone.utc).isoformat()
    reply_sent = False
    send_raw: dict[str, Any] | None = None
    is_itiraz = decision.intent == "itiraz"

    should_send = (
        bool(decision.reply_text.strip())
        and decision.intent in _SENDABLE_INTENTS
        and decision.confidence >= 0.5
    )

    if should_send and not dry_run:
        zernio = get_zernio_client()
        lead_row = _resolve_lead_row(nocodb, leads_table, inbound_row)
        phone = (lead_row or {}).get("telefon") or ""
        if not phone:
            log.warning("auto_reply: lead phone missing row_id=%s", row_id)
        else:
            conv = await zernio.find_conversation_by_phone(phone)
            conv_id = (conv or {}).get("id") or (conv or {}).get("conversationId")
            if not conv_id:
                log.warning("auto_reply: no conversation for phone=%s", phone)
            else:
                send_raw = await zernio.send_message(conv_id, decision.reply_text)
                reply_sent = True
                contact = (conv or {}).get("contact") or {}
                contact_id = contact.get("id")
                if contact_id:
                    try:
                        existing = list(contact.get("tags") or [])
                        merged = sorted(
                            set(existing + ["hot_lead", "oto_yanit_gonderildi"])
                        )
                        await zernio.tag_contact(contact_id, merged)
                    except Exception as exc:
                        log.warning(
                            "auto_reply: tag_contact failed contact_id=%s: %s",
                            contact_id, exc,
                        )

    if reply_sent:
        platform_message_id = (
            (send_raw or {}).get("messageId")
            or (send_raw or {}).get("id")
            or f"auto_reply_{row_id}_{int(datetime.now(timezone.utc).timestamp())}"
        )
        try:
            nocodb.upsert_record(
                messages_table,
                "external_message_id",
                {
                    "lead_adi": lead_name,
                    "tarih": timestamp,
                    "kanal": inbound_row.get("kanal") or "WhatsApp",
                    "yon": "Giden",
                    "tur": "Itiraz Yanit" if is_itiraz else "Auto Reply",
                    "mesaj_icerigi": decision.reply_text,
                    "external_message_id": platform_message_id,
                    "agent": "Auto-reply Agent",
                    "otomatik_mi": True,
                    "auto_reply_processed": True,
                },
            )
        except Exception as exc:
            log.warning("auto_reply: outgoing log failed row_id=%s: %s", row_id, exc)

        lead_row = _resolve_lead_row(nocodb, leads_table, inbound_row)
        if lead_row:
            try:
                nocodb.update_record(
                    leads_table,
                    int(lead_row["Id"]),
                    {
                        "asama": "Itiraz" if is_itiraz else "Takipte",
                        "son_temas": timestamp,
                    },
                )
            except Exception as exc:
                log.warning("auto_reply: lead update failed: %s", exc)

    if not dry_run:
        try:
            nocodb.update_record(
                messages_table, int(row_id), {"auto_reply_processed": True}
            )
        except Exception as exc:
            log.warning("auto_reply: cannot mark processed row_id=%s: %s", row_id, exc)

    return {
        "row_id": row_id,
        "intent": decision.intent,
        "confidence": decision.confidence,
        "objection_type": decision.objection_type,
        "reply_sent": reply_sent,
        "history_size": len(history),
        "dry_run": dry_run,
    }


def _resolve_lead_row(
    client: Any, leads_table: str, inbound_row: dict[str, Any]
) -> dict[str, Any] | None:
    name = inbound_row.get("lead_adi")
    if not name:
        return None
    try:
        return client.find_by_field(leads_table, "ad_soyad", name)
    except Exception as exc:
        log.warning("auto_reply: lead lookup failed: %s", exc)
        return None


async def loop(
    config: AutoReplyConfig | None = None, *, max_iterations: int | None = None
) -> None:
    config = config or AutoReplyConfig.from_env()
    settings = get_settings()
    leads_table = settings.nocodb_leads_table_id
    messages_table = settings.nocodb_messages_table_id
    dry_run = settings.dry_run

    if not (leads_table and messages_table):
        log.error("NOCODB tables not configured — auto_reply cannot run")
        return

    log.info(
        "auto_reply starting: poll=%ds batch=%d delay=%d-%ds model=%s dry_run=%s history_limit=%d",
        config.poll_interval_sec,
        config.batch_size,
        config.reply_min_delay_sec,
        config.reply_max_delay_sec,
        config.model,
        dry_run,
        _HISTORY_LIMIT,
    )

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            inbounds = find_pending_inbounds(
                get_nocodb_client(),
                messages_table,
                batch_size=config.batch_size,
                max_age_minutes=config.max_inbound_age_minutes,
            )
            if not inbounds:
                await asyncio.sleep(config.poll_interval_sec)
                continue

            for row in inbounds:
                await asyncio.sleep(config.jitter_delay())
                await handle_one(
                    inbound_row=row,
                    config=config,
                    leads_table=leads_table,
                    messages_table=messages_table,
                    dry_run=dry_run,
                )
            await asyncio.sleep(config.poll_interval_sec)
        except Exception as exc:
            log.exception("auto_reply: loop iteration failed: %s", exc)
            await asyncio.sleep(_PAUSE_ERROR_SEC)


def _install_sigterm_handler() -> None:
    def _stop(*_: object) -> None:
        log.info("auto_reply: SIGTERM received, draining")

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
        pass


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
