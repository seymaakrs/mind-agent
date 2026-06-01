"""Zernio Inbox webhook handler.

Adim 5: Zernio'dan gelen ``message.received`` event'lerini doğrudan mind-agent'a
çekiyoruz — n8n 'Lead Toplama Agent' by-pass. Avantaj: ``upsert_lead``
external_id ile idempotent (aynı kullanıcı 2 mesaj atarsa 1 lead satırı), Adim
3'teki workflow'da bu yoktu.

Akış:

    Zernio -> POST /zernio/webhook (X-Zernio-Signature: sha256=...)
        -> verify_signature
        -> map payload -> Lead fields + external_id (BSUID > phone > sender.id)
        -> upsert_lead (Leadler tablosu)
        -> create Etkilesimler row (yon=Gelen, kanal=WhatsApp/IG DM)

İmza doğrulama soft modda (CLAUDE.md kararı): ``ZERNIO_WEBHOOK_SECRET`` env
yoksa imzasız payload kabul edilir + uyarı log'lanır. Set'lendiğinde header
zorunlu hale gelir, yanlış/eksik imza -> 401.

Sadece ``message.received`` + ``direction=incoming`` lead'e dönüştürülür;
diğer event'ler 200 ack ile no-op.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.app.config import get_settings
from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client
from src.infra.phone import normalize_phone_e164


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


def _expected_signature(secret: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(raw_body: bytes, signature_header: str | None) -> tuple[bool, str]:
    """Return ``(ok, reason)``.

    HMAC zorunlu. ``ZERNIO_WEBHOOK_SECRET`` set degilse webhook reddedilir —
    public endpoint'in spam/saldiri yuzeyi kapatilir. Dev'de env'i set et.
    """
    secret = get_settings().zernio_webhook_secret
    if not secret:
        return False, "ZERNIO_WEBHOOK_SECRET not configured"
    if not signature_header:
        return False, "missing X-Zernio-Signature header"
    expected = _expected_signature(secret, raw_body)
    if not hmac.compare_digest(expected, signature_header):
        return False, "signature mismatch"
    return True, "verified"


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


_KAYNAK_MAP = {
    "whatsapp": "WhatsApp",
    "instagram": "IG DM",
    "facebook": "IG DM",
    # telegram and others fall through to 'Manuel'
}


def derive_external_id(message: dict[str, Any]) -> str:
    """Stable identity for idempotency.

    Priority: BSUID (Meta canonical, WA rollout) > phoneNumber (E.164) >
    sender.id. The chosen anchor is namespaced by ``zernio_<platform>_<kind>_``
    so it never collides with other channel external_ids (e.g. Meta Lead Ads
    leadgen ids).
    """
    sender = message.get("sender") or {}
    platform = (message.get("platform") or "unknown").lower()
    bsuid = sender.get("businessScopedUserId")
    phone_raw = sender.get("phoneNumber")
    if bsuid:
        return f"zernio_{platform}_bsuid_{bsuid}"
    if phone_raw:
        # NOTE: existing rows pre-fix may have un-normalized phone in
        # external_id; new rows will be canonical E.164.
        normalized = normalize_phone_e164(phone_raw) or phone_raw
        return f"zernio_{platform}_phone_{normalized}"
    sender_id = sender.get("id") or "unknown"
    return f"zernio_{platform}_id_{sender_id}"


def _normalize_phone(sender: dict[str, Any]) -> str | None:
    phone = (sender.get("phoneNumber") or "").strip()
    if phone:
        norm = normalize_phone_e164(phone)
        if norm:
            return norm
    sid = (sender.get("id") or "").strip()
    if sid.isdigit() and len(sid) >= 8:
        norm = normalize_phone_e164("+" + sid)
        if norm:
            return norm
        return "+" + sid
    return None


def map_to_lead_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate a Zernio ``message.received`` envelope to upsert_lead fields.

    Inbound mesaj != qualified lead. Bu fonksiyon sadece minimum iletisim
    kaydi olusturur; qualified=false, asama='Yeni'. Sektor/sirket varsayimi
    yapilmaz — qualifier agent insan/LLM onayindan sonra doldurur.
    """
    message = payload.get("message") or {}
    sender = message.get("sender") or {}
    conversation = payload.get("conversation") or {}
    platform = (message.get("platform") or "").lower()

    name = sender.get("name") or conversation.get("participantName") or "Unknown"
    phone = _normalize_phone(sender)
    text = (message.get("text") or "").strip()
    kaynak = _KAYNAK_MAP.get(platform, "Manuel")

    fields: dict[str, Any] = {
        "external_id": derive_external_id(message),
        "ad_soyad": name,
        "kaynak": kaynak,
        "source_workflow_id": "mind_agent_zernio_webhook",
        "asama": "Yeni",
        "qualified": False,
        "lead_skoru": _score(platform),
    }
    if phone:
        fields["telefon"] = phone
    if text:
        fields["notlar"] = text
        fields["ihtiyac_notu"] = f"Zernio {platform}: {text[:200]}"
    return fields


def _score(platform: str) -> int:
    """Inbound conversation skoru — yalniz iletisim sinyali, asla 'sicak' esigi.

    Gercek lead skoru qualifier agent tarafindan (LLM + ICP fit) hesaplanir.
    Bu fonksiyon sadece kanal guvenilirligi icin kucuk bir taban verir.
    """
    if platform == "whatsapp":
        return 15
    if platform in {"instagram", "facebook"}:
        return 10
    return 5


def map_to_message_fields(payload: dict[str, Any], lead_name: str) -> dict[str, Any]:
    """Translate to an Etkilesimler row keyed by external_message_id (idempotent)."""
    message = payload.get("message") or {}
    platform = (message.get("platform") or "").lower()
    kanal = _KAYNAK_MAP.get(platform, "Manuel")
    return {
        "lead_adi": lead_name,
        "tarih": datetime.now(timezone.utc).isoformat(),
        "kanal": kanal,
        "yon": "Gelen",
        "tur": "Yanit",
        "mesaj_icerigi": message.get("text") or "",
        "external_message_id": message.get("platformMessageId") or message.get("id"),
        "agent": "Zernio Webhook",
        "otomatik_mi": True,
        # Auto-reply worker (Adim 6) picks rows where this is False. Webhook
        # writes incoming messages with False so the responder loop can claim
        # them; responder flips to True after sending the reply.
        "auto_reply_processed": False,
    }


# ---------------------------------------------------------------------------
# Handler entry-point
# ---------------------------------------------------------------------------


def is_target_event(payload: dict[str, Any]) -> bool:
    """Only ``message.received`` with ``direction=incoming`` becomes a lead."""
    if payload.get("event") != "message.received":
        return False
    msg = payload.get("message") or {}
    return msg.get("direction") == "incoming"


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    """Drive the lead + interaction writes. Returns a structured response.

    Non-target events (post.published, account.connected, etc.) are
    short-circuited with ``{"success": True, "skipped": true, "reason": ...}``.
    """
    event = payload.get("event") or "<missing>"
    if not is_target_event(payload):
        log.info("zernio webhook: skipping event=%s", event)
        return {"success": True, "skipped": True, "reason": f"event={event} ignored"}

    settings = get_settings()
    leads_tbl = settings.nocodb_leads_table_id
    msgs_tbl = settings.nocodb_messages_table_id

    # Inbound mesaj != qualified lead. Default: lead satiri yazma, sadece
    # Etkilesimler'e log dus. Lead promotion'u qualifier agent yapar.
    create_lead = os.getenv("ZERNIO_WEBHOOK_CREATE_LEAD", "false").lower() == "true"

    lead_fields = map_to_lead_fields(payload)
    client = get_nocodb_client()
    result: dict[str, Any] = {
        "success": True,
        "external_id": lead_fields["external_id"],
        "lead_created": False,
    }
    lead_record: dict[str, Any] = {}

    if create_lead and leads_tbl:
        try:
            lead_result = client.upsert_record(leads_tbl, "external_id", lead_fields)
            lead_record = lead_result["record"]
            result["lead_created"] = lead_result["created"]
            result["lead_id"] = lead_record.get("Id")
        except Exception as exc:
            return classify_error(exc, "nocodb")

    if msgs_tbl:
        msg_fields = map_to_message_fields(payload, (lead_record.get("ad_soyad") if lead_record else None) or lead_fields["ad_soyad"])
        try:
            ext_msg_id = msg_fields.get("external_message_id")
            if ext_msg_id:
                msg_result = client.upsert_record(msgs_tbl, "external_message_id", msg_fields)
                result["message_id"] = msg_result["record"].get("Id")
                result["message_created"] = msg_result["created"]
            else:
                msg_record = client.create_record(msgs_tbl, msg_fields)
                result["message_id"] = msg_record.get("Id")
                result["message_created"] = True
        except Exception as exc:
            log.warning("zernio webhook: failed to log Etkilesimler: %s", exc)
            result["message_log_error"] = str(exc)
    return result


__all__ = [
    "verify_signature",
    "derive_external_id",
    "map_to_lead_fields",
    "map_to_message_fields",
    "is_target_event",
    "handle",
]
