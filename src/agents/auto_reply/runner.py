"""Auto-reply Agent main loop — Cloud Run job entry-point.

    python -m src.agents.auto_reply.runner

Polling-based (60sn). Each tick:
1. Query Etkilesimler for unprocessed inbound rows (oldest first, max age 60dk).
2. For each row: jitter 30-60sn (Seyma's lead_monitor cadence), call
   ``responder.decide_reply``, optionally send via Zernio, log outgoing
   message, mark inbound row processed, flip lead.asama.
3. DRY_RUN gates Zernio + NocoDB writes (still classifies for shadow log).

Itiraz (Faz 1): ``AUTO_REPLY_ITIRAZ_NATIVE`` acikken itiraz tespitinde
responder'in urettigi ONERI taslagi + objection_type kullanilir;
Etkilesimler'e 'Itiraz Önerisi' satiri yazilir ve n8n'e taslakla birlikte
iletilir (Seyma onayli, musteriye OTOMATIK gitmez). Flag kapaliyken eski
'Itiraz Handoff' davranisi aynen korunur (regresyon yok).
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

from src.agents.auto_reply.policy import AutoReplyConfig
from src.agents.auto_reply.responder import AutoReplyDecision, decide_reply
from src.agents.auto_reply.targeting import find_pending_inbounds
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client
from src.infra.zernio import get_zernio_client


log = logging.getLogger("auto_reply")

_PAUSE_ERROR_SEC = 60


def _itiraz_native_enabled() -> bool:
    """Faz 1 feature flag. Kapaliyken eski n8n handoff davranisi gecerli."""
    return os.environ.get("AUTO_REPLY_ITIRAZ_NATIVE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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

    decision: AutoReplyDecision = await decide_reply(text, config=config)
    log.info(
        "auto_reply: classify row_id=%s intent=%s conf=%.2f obj=%s will_reply=%s",
        row_id,
        decision.intent,
        decision.confidence,
        decision.objection_type,
        bool(decision.reply_text),
    )

    nocodb = get_nocodb_client()
    timestamp = datetime.now(timezone.utc).isoformat()
    reply_sent = False
    send_raw: dict[str, Any] | None = None

    should_send = (
        bool(decision.reply_text.strip())
        and decision.intent in {"olumlu", "soru"}
        and decision.confidence >= 0.5
    )

    if should_send and not dry_run:
        zernio = get_zernio_client()
        # Inbound just arrived — we're inside the 24h CS window, free-form OK.
        # We need a conversation_id; look it up by lead phone.
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
                # Mirror Seyma's lead_monitor.py tagging behaviour: mark the
                # contact as hot + auto-reply sent so Beyza's Zernio panel
                # segments stay in sync.
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
                    "tur": "Auto Reply",
                    "mesaj_icerigi": decision.reply_text,
                    "external_message_id": platform_message_id,
                    "agent": "Auto-reply Agent",
                    "otomatik_mi": True,
                    "auto_reply_processed": True,
                },
            )
        except Exception as exc:
            log.warning("auto_reply: outgoing log failed row_id=%s: %s", row_id, exc)

        # Promote lead lifecycle: Sicak -> Takipte
        lead_row = _resolve_lead_row(nocodb, leads_table, inbound_row)
        if lead_row:
            try:
                nocodb.update_record(
                    leads_table,
                    int(lead_row["Id"]),
                    {
                        "asama": "Takipte",
                        "son_temas": timestamp,
                    },
                )
            except Exception as exc:
                log.warning("auto_reply: lead update failed: %s", exc)

    # ----- Itiraz handoff (intent=itiraz) -----
    # Auto-reply musteriye OTOMATIK yanit ATMAZ. Faz 1: native flag acikken
    # responder'in urettigi ONERI taslagi + objection_type ile n8n'e
    # iletilir ve 'Itiraz Önerisi' loglanir; flag kapaliyken eski
    # 'Itiraz Handoff' davranisi aynen korunur.
    handoff_sent = False
    if decision.intent == "itiraz" and decision.confidence >= 0.5 and not dry_run:
        native = _itiraz_native_enabled()
        draft_reply = decision.reply_text.strip() if native else ""
        objection_type = decision.objection_type if native else None
        try:
            handoff_sent = await _handoff_to_n8n_itiraz(
                inbound_text=text,
                lead_name=lead_name,
                lead_email=(inbound_row.get("lead_email") or ""),
                draft_reply=draft_reply,
                objection_type=objection_type,
            )
        except Exception as exc:
            log.warning("auto_reply: itiraz handoff failed row_id=%s: %s", row_id, exc)

        # Lead asama: Itiraz (yeni SingleSelect option — migration ile eklenir)
        lead_row = _resolve_lead_row(nocodb, leads_table, inbound_row)
        if lead_row:
            try:
                nocodb.update_record(
                    leads_table,
                    int(lead_row["Id"]),
                    {"asama": "Itiraz", "son_temas": timestamp},
                )
            except Exception as exc:
                log.warning("auto_reply: lead asama->Itiraz failed: %s", exc)

        # Etkilesimler log. native: 'Itiraz Önerisi' (taslak dahil),
        # aksi halde eski 'Itiraz Handoff'. (yeni SingleSelect option —
        # migration ile eklenir)
        if messages_table:
            if native:
                log_tur = "Itiraz Önerisi"
                log_body = (
                    f"Auto-reply itiraz tespit etti (tip={objection_type}). "
                    f"Seyma onayina dusen ONERI taslagi:\n\n{draft_reply}\n\n"
                    f"Orijinal mesaj: {text[:200]}"
                )
                log_prefix = "itiraz_oneri"
            else:
                log_tur = "Itiraz Handoff"
                log_body = (
                    "Auto-reply intent=itiraz tespit etti, n8n Itiraz Agent'a "
                    f"handoff edildi. Orijinal: {text[:200]}"
                )
                log_prefix = "itiraz_handoff"
            try:
                nocodb.upsert_record(
                    messages_table,
                    "external_message_id",
                    {
                        "lead_adi": lead_name,
                        "tarih": timestamp,
                        "kanal": inbound_row.get("kanal") or "WhatsApp",
                        "yon": "Giden",
                        "tur": log_tur,
                        "mesaj_icerigi": log_body,
                        "external_message_id": f"{log_prefix}_{row_id}_{int(datetime.now(timezone.utc).timestamp())}",
                        "agent": "Auto-reply Agent",
                        "otomatik_mi": True,
                        "auto_reply_processed": True,
                    },
                )
            except Exception as exc:
                log.warning("auto_reply: itiraz log failed: %s", exc)

    if not dry_run:
        try:
            nocodb.update_record(
                messages_table, int(row_id), {"auto_reply_processed": True}
            )
        except Exception as exc:
            log.warning("auto_reply: cannot mark processed row_id=%s: %s", row_id, exc)

    return {
        "handoff_sent": handoff_sent,
        "row_id": row_id,
        "intent": decision.intent,
        "confidence": decision.confidence,
        "objection_type": decision.objection_type,
        "reply_sent": reply_sent,
        "dry_run": dry_run,
    }


async def _handoff_to_n8n_itiraz(
    *,
    inbound_text: str,
    lead_name: str,
    lead_email: str,
    draft_reply: str = "",
    objection_type: str | None = None,
) -> bool:
    """Auto-reply intent=itiraz tespit ettiginde n8n Itiraz Agent
    webhook'una POST. n8n Seyma'ya oneri maili gonderir (insan onayli,
    otomatik musteriye yollamaz).

    Faz 1: ``draft_reply`` ve ``objection_type`` verildiyse (native flag),
    bizim urettigimiz oneri taslagi + itiraz tipi de body'ye eklenir; n8n
    Gemini siniflandirmasina ihtiyac duymadan dogrudan maile koyabilir.
    Eski cagri sekli (sadece text) backward-compatible kalir.

    Returns True if webhook 2xx donduyse.
    """
    from src.tools.n8n_bridge_tools import _call_n8n_workflow_impl
    body: dict[str, Any] = {
        "musteri_email": lead_email or f"{lead_name.replace(' ', '_')}@unknown",
        "mesaj": inbound_text,
    }
    if draft_reply:
        body["oneri_yaniti"] = draft_reply
    if objection_type:
        body["itiraz_tipi"] = objection_type
    result = await _call_n8n_workflow_impl(name="itiraz_agent", body=body)
    ok = bool(result.get("success"))
    if ok:
        log.info("auto_reply: itiraz handoff to n8n OK (lead=%s)", lead_name)
    else:
        log.warning(
            "auto_reply: itiraz handoff to n8n FAILED: %s",
            result.get("user_message_tr") or result.get("error"),
        )
    return ok


def _resolve_lead_row(
    client: Any, leads_table: str, inbound_row: dict[str, Any]
) -> dict[str, Any] | None:
    """Best-effort lookup of the lead behind an Etkilesimler row by lead_adi."""
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
        "auto_reply starting: poll=%ds batch=%d delay=%d-%ds model=%s dry_run=%s itiraz_native=%s",
        config.poll_interval_sec,
        config.batch_size,
        config.reply_min_delay_sec,
        config.reply_max_delay_sec,
        config.model,
        dry_run,
        _itiraz_native_enabled(),
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
