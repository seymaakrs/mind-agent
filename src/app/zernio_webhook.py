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
from datetime import datetime, timezone
from typing import Any

from src.app.config import get_settings
from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


def _expected_signature(secret: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(raw_body: bytes, signature_header: str | None) -> tuple[bool, str]:
    """Return ``(ok, reason)``.

    Soft mode: when ``ZERNIO_WEBHOOK_SECRET`` is unset, returns ``(True, "skipped")``
    so dev/test environments can drive the webhook without configuring HMAC.
    """
    secret = get_settings().zernio_webhook_secret
    if not secret:
        return True, "skipped (no ZERNIO_WEBHOOK_SECRET)"
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
    phone = sender.get("phoneNumber")
    if bsuid:
        return f"zernio_{platform}_bsuid_{bsuid}"
    if phone:
        return f"zernio_{platform}_phone_{phone}"
    sender_id = sender.get("id") or "unknown"
    return f"zernio_{platform}_id_{sender_id}"


def _normalize_phone(sender: dict[str, Any]) -> str | None:
    phone = (sender.get("phoneNumber") or "").strip()
    if phone:
        return phone
    sid = (sender.get("id") or "").strip()
    if sid.isdigit() and len(sid) >= 8:
        return "+" + sid
    return None


def map_to_lead_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate a Zernio ``message.received`` envelope to upsert_lead fields.

    Returns a dict compatible with NocoDB Leadler columns. Caller decides
    whether to write — non-incoming or non-target events should be filtered
    upstream.
    """
    message = payload.get("message") or {}
    sender = message.get("sender") or {}
    conversation = payload.get("conversation") or {}
    platform = (message.get("platform") or "").lower()

    name = sender.get("name") or conversation.get("participantName") or "Unknown"
    phone = _normalize_phone(sender)
    text = (message.get("text") or "").strip()
    kaynak = _KAYNAK_MAP.get(platform, "Manuel")
    sektor_default = "Otelcilik" if platform == "whatsapp" else None
    asama = "Sicak" if message.get("direction") == "incoming" else "Yeni"

    fields: dict[str, Any] = {
        "external_id": derive_external_id(message),
        "ad_soyad": name,
        "sirket_adi": name,  # Slowdays WA: gönderen adı = otel adı
        "kaynak": kaynak,
        "source_workflow_id": "mind_agent_zernio_webhook",
        "asama": asama,
        "lead_skoru": _score(platform, sektor_default, asama),
    }
    if phone:
        fields["telefon"] = phone
    if sektor_default:
        fields["sektor"] = sektor_default
    if text:
        fields["notlar"] = text
        fields["ihtiyac_notu"] = f"Zernio {platform}: {text[:200]}"
    return fields


def _score(platform: str, sektor: str | None, asama: str) -> int:
    """Match the n8n Calculate Lead Score formula (Adim 3 jsCode)."""
    skor = 0
    if sektor in {"Otelcilik", "Yeme-Icme", "Turizm", "Spa-Wellness"}:
        skor += 20
    elif sektor and sektor != "Diger":
        skor += 10
    # konum unknown from Zernio payload — skip
    if platform == "whatsapp":
        skor += 20  # 'WhatsApp' kaynagi
    elif platform in {"instagram", "facebook"}:
        skor += 10
    else:
        skor += 5
    if asama == "Sicak":
        skor += 30
    elif asama == "Ilik":
        skor += 20
    elif asama == "Yeni":
        skor += 5
    return skor


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
    if not leads_tbl:
        return {
            "success": False,
            "error": "NOCODB_LEADS_TABLE_ID is not configured",
            "error_code": "INVALID_INPUT",
        }

    lead_fields = map_to_lead_fields(payload)
    try:
        client = get_nocodb_client()
        lead_result = client.upsert_record(leads_tbl, "external_id", lead_fields)
        lead_record = lead_result["record"]
        result: dict[str, Any] = {
            "success": True,
            "created": lead_result["created"],
            "lead_id": lead_record.get("Id"),
            "external_id": lead_fields["external_id"],
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")

    # Best-effort message log; failure does not roll back the lead upsert.
    if msgs_tbl:
        msg_fields = map_to_message_fields(payload, lead_record.get("ad_soyad") or lead_fields["ad_soyad"])
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
