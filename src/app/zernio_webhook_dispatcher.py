"""Zernio webhook event dispatcher (Part 1 — webhook expansion).

This module lives next to ``zernio_webhook.py``. The legacy
``zernio_webhook.handle()`` keeps the original ``message.received`` →
NocoDB Lead/Etkilesimler flow IDENTICAL — Slowdays parity is non-negotiable.
All NEW events are routed through ``dispatch()`` here.

Each handler returns an ``EventDecision`` dict
``{action, reason, side_effects: {...}}`` for audit/test friendliness.

Smart parameters:

- LRU replay guard (in-memory, no Redis) on event id
- Per-event feature flags: ``ZERNIO_EVENT_<NAME>_ENABLED`` (default true)
- ``business_id`` resolver: ``account_id`` → Firestore lookup, 5min cache
- Unknown events → 200 ack + warn (never 500)
"""
from __future__ import annotations

import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable


log = logging.getLogger("zernio_webhook_dispatcher")


_EVENT_ID_CACHE_SIZE = 512
_event_id_cache: "OrderedDict[str, float]" = OrderedDict()
_business_resolver_cache: dict[str, tuple[str, float]] = {}
_BUSINESS_RESOLVER_TTL_SEC = 300


# Local copy of the legacy kanal map (kept in sync with zernio_webhook._KAYNAK_MAP).
_KAYNAK_MAP = {
    "whatsapp": "WhatsApp",
    "instagram": "IG DM",
    "facebook": "IG DM",
}


# --- Indirections so tests can monkeypatch without importing firebase_admin --


def _get_firestore() -> Any:
    from src.infra.firebase_client import get_firestore_client

    return get_firestore_client()


def _get_nocodb() -> Any:
    from src.infra.nocodb_client import get_nocodb_client

    return get_nocodb_client()


# --- Replay / flag / resolver helpers ---------------------------------------


def _event_id(payload: dict[str, Any]) -> str | None:
    eid = payload.get("id") or payload.get("eventId") or payload.get("event_id")
    return str(eid) if eid else None


def _seen_recently(event_id: str) -> bool:
    if event_id in _event_id_cache:
        _event_id_cache.move_to_end(event_id)
        return True
    _event_id_cache[event_id] = 0.0
    while len(_event_id_cache) > _EVENT_ID_CACHE_SIZE:
        _event_id_cache.popitem(last=False)
    return False


def _reset_replay_cache() -> None:
    """Test helper."""
    _event_id_cache.clear()
    _business_resolver_cache.clear()


def _event_enabled(event: str) -> bool:
    flag_name = "ZERNIO_EVENT_" + event.upper().replace(".", "_") + "_ENABLED"
    val = (os.environ.get(flag_name) or "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def _resolve_business_id(payload: dict[str, Any]) -> str | None:
    import time

    direct = payload.get("businessId") or payload.get("business_id")
    if direct:
        return str(direct)
    account = payload.get("account") or {}
    account_id = account.get("id") or payload.get("account_id")
    if not account_id:
        return None
    account_id = str(account_id)
    now = time.time()
    cached = _business_resolver_cache.get(account_id)
    if cached and (now - cached[1]) < _BUSINESS_RESOLVER_TTL_SEC:
        return cached[0]
    try:
        db = _get_firestore()
        q = (
            db.collection("businesses")
            .where("zernio_account_id", "==", account_id)
            .limit(1)
            .stream()
        )
        for doc in q:
            bid = doc.id
            _business_resolver_cache[account_id] = (bid, now)
            return bid
    except Exception as exc:
        log.warning("business_id resolver failed: %s", exc)
    return None


def _decision(action: str, reason: str, **side_effects: Any) -> dict[str, Any]:
    return {"action": action, "reason": reason, "side_effects": side_effects}


# --- Per-event handlers -----------------------------------------------------


def _handle_post_published(payload: dict[str, Any]) -> dict[str, Any]:
    post = payload.get("post") or {}
    post_id = post.get("id") or payload.get("postId")
    business_id = _resolve_business_id(payload)
    if not (post_id and business_id):
        return _decision("skipped", "missing post_id or business_id")
    try:
        db = _get_firestore()
        ref = (
            db.collection("businesses")
            .document(business_id)
            .collection("instagram_posts")
            .document(str(post_id))
        )
        ref.set(
            {
                "status": "published",
                "published_at": post.get("publishedAt")
                or datetime.now(timezone.utc).isoformat(),
                "platform_post_url": post.get("permalink") or post.get("url"),
            },
            merge=True,
        )
        return _decision(
            "post_marked_published",
            "firestore updated",
            firestore_path=f"businesses/{business_id}/instagram_posts/{post_id}",
        )
    except Exception as exc:
        log.warning("post.published firestore write failed: %s", exc)
        return _decision("error", f"firestore write failed: {exc}")


def _handle_post_failed(payload: dict[str, Any]) -> dict[str, Any]:
    post = payload.get("post") or {}
    business_id = _resolve_business_id(payload)
    error_msg = payload.get("error") or post.get("errorMessage") or "unknown"
    side: dict[str, Any] = {}
    try:
        db = _get_firestore()
        db.collection("errors").add(
            {
                "agent": "zernio_webhook",
                "task": "post.failed",
                "business_id": business_id,
                "post_id": post.get("id"),
                "error_message": str(error_msg),
                "severity": "high",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "raw_payload": payload,
            }
        )
        side["errors_logged"] = True
    except Exception as exc:
        log.warning("post.failed errors write: %s", exc)
        side["errors_logged"] = False
    url = os.environ.get("GUARDIAN_ALERT_WEBHOOK_URL")
    if url:
        try:
            import httpx

            with httpx.Client(timeout=10.0) as client:
                client.post(
                    url,
                    json={
                        "kind": "post_failed",
                        "business_id": business_id,
                        "post_id": post.get("id"),
                        "error": str(error_msg),
                    },
                )
            side["alert_sent"] = True
        except Exception as exc:
            log.warning("bekci alert failed: %s", exc)
            side["alert_sent"] = False
    return _decision("post_failed_logged", "alerted ops", **side)


def _handle_account_disconnected(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account") or {}
    platform = (account.get("platform") or payload.get("platform") or "unknown").lower()
    reason = payload.get("reason") or "unknown"
    business_id = _resolve_business_id(payload)
    side: dict[str, Any] = {"platform": platform}
    if business_id:
        try:
            db = _get_firestore()
            db.collection("businesses").document(business_id).set(
                {
                    "connections": {
                        platform: {
                            "status": "disconnected",
                            "disconnected_at": datetime.now(timezone.utc).isoformat(),
                            "reason": str(reason),
                        }
                    }
                },
                merge=True,
            )
            side["firestore_updated"] = True
        except Exception as exc:
            log.warning("account.disconnected firestore: %s", exc)
            side["firestore_updated"] = False
    try:
        from src.app.config import get_settings

        settings = get_settings()
        if settings.nocodb_messages_table_id:
            _get_nocodb().create_record(
                settings.nocodb_messages_table_id,
                {
                    "tarih": datetime.now(timezone.utc).isoformat(),
                    "kanal": "Manuel",
                    "yon": "Giden",
                    "tur": "bildirim",
                    "mesaj_icerigi": f"Hesap baglantisi koptu ({platform}). Sebep: {reason}",
                    "agent": "Zernio Webhook",
                    "otomatik_mi": True,
                },
            )
            side["seyma_notified"] = True
    except Exception as exc:
        log.warning("notify_seyma write failed: %s", exc)
        side["seyma_notified"] = False
    return _decision("account_disconnected", f"{platform} disconnected", **side)


def _handle_comment_received(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from src.agents.comment_to_dm.runner import handle_comment

        result = handle_comment(payload, business_id=_resolve_business_id(payload))
        return _decision(
            result.get("action", "comment_processed"),
            result.get("reason", "dispatched to comment_to_dm"),
            **{k: v for k, v in result.items() if k not in ("action", "reason")},
        )
    except Exception as exc:
        log.warning("comment_to_dm dispatch failed: %s", exc)
        return _decision("error", f"comment_to_dm failed: {exc}")


def _handle_message_sent(payload: dict[str, Any]) -> dict[str, Any]:
    from src.app.config import get_settings

    message = payload.get("message") or {}
    ext_id = message.get("platformMessageId") or message.get("id")
    if not ext_id:
        return _decision("skipped", "no external_message_id")
    settings = get_settings()
    if not settings.nocodb_messages_table_id:
        return _decision("skipped", "no messages table configured")
    fields = {
        "tarih": message.get("sentAt") or datetime.now(timezone.utc).isoformat(),
        "kanal": _KAYNAK_MAP.get((message.get("platform") or "").lower(), "Manuel"),
        "yon": "Giden",
        "tur": "Yanit",
        "mesaj_icerigi": message.get("text") or "",
        "external_message_id": ext_id,
        "agent": "Zernio Webhook",
        "otomatik_mi": True,
        "auto_reply_processed": True,
    }
    try:
        client = _get_nocodb()
        res = client.upsert_record(
            settings.nocodb_messages_table_id, "external_message_id", fields
        )
        return _decision(
            "message_sent_logged",
            "etkilesimler upsert",
            message_id=res.get("record", {}).get("Id"),
            created=res.get("created"),
        )
    except Exception as exc:
        log.warning("message.sent upsert failed: %s", exc)
        return _decision("error", f"upsert failed: {exc}")


def _handle_post_boost_completed(payload: dict[str, Any]) -> dict[str, Any]:
    business_id = _resolve_business_id(payload)
    campaign = payload.get("campaign") or {}
    campaign_id = campaign.get("id") or payload.get("campaignId")
    if not (business_id and campaign_id):
        return _decision("skipped", "missing business_id or campaign_id")
    try:
        db = _get_firestore()
        ref = (
            db.collection("businesses")
            .document(business_id)
            .collection("ads_history")
            .document(str(campaign_id))
        )
        ref.set(
            {
                "campaign_id": str(campaign_id),
                "post_id": payload.get("postId") or campaign.get("postId"),
                "spend": campaign.get("spend") or payload.get("spend"),
                "ctr": campaign.get("ctr") or payload.get("ctr"),
                "impressions": campaign.get("impressions"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            },
            merge=True,
        )
        return _decision(
            "boost_logged",
            "ads_history updated",
            firestore_path=f"businesses/{business_id}/ads_history/{campaign_id}",
        )
    except Exception as exc:
        log.warning("post.boost.completed write failed: %s", exc)
        return _decision("error", f"firestore write failed: {exc}")


def _handle_message_received_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap legacy handle() in the dispatcher contract for completeness."""
    from src.app.zernio_webhook import handle as legacy_handle

    legacy = legacy_handle(payload)
    return _decision(
        "legacy_message_received",
        "ok" if legacy.get("success") else legacy.get("error", "error"),
        **{k: v for k, v in legacy.items()},
    )


EVENT_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "message.received": _handle_message_received_v2,
    "post.published": _handle_post_published,
    "post.failed": _handle_post_failed,
    "account.disconnected": _handle_account_disconnected,
    "comment.received": _handle_comment_received,
    "message.sent": _handle_message_sent,
    "post.boost.completed": _handle_post_boost_completed,
}


def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    """Route a Zernio webhook event to its handler.

    Returns ``{success, event, decision, replay?, disabled?}``. Always
    returns success=True for events we recognize the wire shape of —
    unknown events are acked 200 with action=skipped + warn log.
    """
    event = payload.get("event") or "<missing>"
    event_id = _event_id(payload)
    if event_id and _seen_recently(event_id):
        log.warning("replay event_id=%s event=%s", event_id, event)
        return {
            "success": True,
            "event": event,
            "replay": True,
            "decision": _decision("skipped", f"replay event_id={event_id}"),
        }
    if not _event_enabled(event):
        log.info("event disabled event=%s", event)
        return {
            "success": True,
            "event": event,
            "disabled": True,
            "decision": _decision("skipped", "feature flag disabled"),
        }
    handler = EVENT_HANDLERS.get(event)
    if handler is None:
        log.warning("unknown event=%s — ack only", event)
        return {
            "success": True,
            "event": event,
            "decision": _decision("skipped", f"unknown event {event}"),
        }
    try:
        decision = handler(payload)
    except Exception as exc:
        log.exception("handler crashed event=%s", event)
        return {
            "success": True,
            "event": event,
            "decision": _decision("error", f"handler crashed: {exc}"),
        }
    return {"success": True, "event": event, "decision": decision}


__all__ = [
    "dispatch",
    "EVENT_HANDLERS",
    "_reset_replay_cache",
    "_get_firestore",
    "_get_nocodb",
]
