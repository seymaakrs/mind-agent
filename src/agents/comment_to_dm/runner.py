"""Comment-to-DM entry-point — called by the Zernio webhook dispatcher.

``handle_comment(event_payload, business_id=...)`` does the full
classifier → decision → DM/like/tag flow and returns an audit dict.

This is intentionally synchronous (matches the webhook handler contract).
The classifier itself is async, so we drive it with ``asyncio.run`` here.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.agents.comment_to_dm.classifier import (
    CommentClassification,
    classify_comment,
)
from src.agents.comment_to_dm.policy import (
    CommentToDMConfig,
    already_dm_d_recently,
    keyword_check,
)
from src.agents.comment_to_dm.responder import CommentDecision, decide


log = logging.getLogger("comment_to_dm")


def _get_firestore() -> Any:
    """Indirection — tests monkeypatch this so firebase_admin import is avoided."""
    from src.infra.firebase_client import get_firestore_client

    return get_firestore_client()


def _get_zernio() -> Any:
    from src.infra.zernio import get_zernio_client

    return get_zernio_client()


def _get_nocodb() -> Any:
    from src.infra.nocodb_client import get_nocodb_client

    return get_nocodb_client()


def _load_config(business_id: str | None) -> CommentToDMConfig:
    """Load Firestore comment_to_dm config. Returns default disabled cfg on error."""
    if not business_id:
        return CommentToDMConfig()
    try:
        db = _get_firestore()
        doc = (
            db.collection("businesses")
            .document(business_id)
            .collection("comment_to_dm")
            .document("config")
            .get()
        )
        data = doc.to_dict() if doc.exists else None
        return CommentToDMConfig.from_doc(data)
    except Exception as exc:
        log.warning("comment_to_dm: config load failed: %s", exc)
        return CommentToDMConfig()


def _idempotency_doc_id(post_id: str, author_id: str) -> str:
    safe = f"{post_id}__{author_id}".replace("/", "_")
    return safe[:1500]  # firestore doc id length sanity cap


def _check_idempotency(
    business_id: str | None, post_id: str, author_id: str
) -> tuple[bool, str | None]:
    """Return ``(ok_to_send, last_sent_at)``."""
    if not business_id:
        return True, None
    try:
        db = _get_firestore()
        ref = (
            db.collection("businesses")
            .document(business_id)
            .collection("comment_to_dm_sent")
            .document(_idempotency_doc_id(post_id, author_id))
        )
        snap = ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            sent_at = data.get("sent_at")
            if already_dm_d_recently(sent_at):
                return False, sent_at
        return True, None
    except Exception as exc:
        log.warning("comment_to_dm: idempotency check failed: %s", exc)
        return True, None


def _record_dm_sent(
    business_id: str | None,
    post_id: str,
    author_id: str,
    *,
    intent: str,
) -> None:
    if not business_id:
        return
    try:
        db = _get_firestore()
        db.collection("businesses").document(business_id).collection(
            "comment_to_dm_sent"
        ).document(_idempotency_doc_id(post_id, author_id)).set(
            {
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "intent": intent,
                "post_id": post_id,
                "author_id": author_id,
            }
        )
    except Exception as exc:
        log.warning("comment_to_dm: idempotency record failed: %s", exc)


def _send_dm(author_id: str, platform: str, text: str) -> dict[str, Any]:
    """Best-effort DM via Zernio inbox client. Returns ``{ok, error?}``."""
    try:
        client = _get_zernio()
        # send_message is the canonical inbox send — see src/infra/zernio/inbox.py
        result = client.send_message(
            recipient_id=author_id, text=text, platform=platform
        )
        return {"ok": True, "result": result}
    except Exception as exc:
        log.warning("comment_to_dm: send_message failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def _like_comment(comment_id: str) -> bool:
    try:
        client = _get_zernio()
        # Zernio social API; method name follows IG comment endpoint convention
        if hasattr(client, "like_comment"):
            client.like_comment(comment_id)
            return True
    except Exception as exc:
        log.warning("comment_to_dm: like_comment failed: %s", exc)
    return False


def _tag_spam(comment_id: str) -> bool:
    try:
        client = _get_zernio()
        if hasattr(client, "tag_comment"):
            client.tag_comment(comment_id, tag="spam")
            return True
        if hasattr(client, "hide_comment"):
            client.hide_comment(comment_id)
            return True
    except Exception as exc:
        log.warning("comment_to_dm: tag_spam failed: %s", exc)
    return False


def _notify_seyma_complaint(business_id: str | None, payload: dict[str, Any]) -> bool:
    """Write a bildirim row to Etkilesimler so Sema sees it in real time."""
    try:
        from src.app.config import get_settings
        settings = get_settings()
        if not settings.nocodb_messages_table_id:
            return False
        comment = payload.get("comment") or {}
        _get_nocodb().create_record(
            settings.nocodb_messages_table_id,
            {
                "tarih": datetime.now(timezone.utc).isoformat(),
                "kanal": "IG DM",
                "yon": "Giden",
                "tur": "bildirim",
                "mesaj_icerigi": (
                    f"Sikayet yorumu (business={business_id}): "
                    f"{comment.get('text', '')[:300]}"
                ),
                "agent": "Comment-to-DM",
                "otomatik_mi": True,
            },
        )
        return True
    except Exception as exc:
        log.warning("comment_to_dm: notify_seyma failed: %s", exc)
        return False


def _classify_sync(text: str) -> CommentClassification:
    """Drive the async classifier from sync context. Resilient to loops."""
    try:
        return asyncio.run(classify_comment(text))
    except RuntimeError:
        # Already inside an event loop (rare in webhook path, defensive).
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(classify_comment(text))
        finally:
            loop.close()


def handle_comment(
    payload: dict[str, Any],
    *,
    business_id: str | None = None,
) -> dict[str, Any]:
    """Main entry-point. Returns an audit dict consumed by the webhook
    dispatcher (so the HTTP response carries the action + reason).

    The flow:
      1. Resolve config (default = disabled)
      2. Whitelist/blacklist keyword gate
      3. Idempotency check (24h per post/author)
      4. Classify intent (LLM)
      5. Map to action (decide)
      6. Execute side-effect (DM / like / notify / tag / ignore)
    """
    comment = payload.get("comment") or {}
    post = payload.get("post") or {}
    author = comment.get("author") or {}
    text = comment.get("text") or ""
    post_id = str(post.get("id") or comment.get("postId") or "")
    author_id = str(author.get("id") or "")
    platform = (comment.get("platform") or "instagram").lower()
    comment_id = str(comment.get("id") or "")

    cfg = _load_config(business_id)
    if not cfg.enabled:
        return {"action": "ignore", "reason": "comment_to_dm disabled for business"}

    ok, why = keyword_check(text, cfg)
    if not ok:
        return {"action": "ignore", "reason": why}

    if post_id and author_id:
        send_ok, last = _check_idempotency(business_id, post_id, author_id)
        if not send_ok:
            return {
                "action": "ignore",
                "reason": "idempotency — DM sent in last 24h",
                "last_sent_at": last,
            }

    classification = _classify_sync(text)
    decision = decide(classification, cfg)
    audit: dict[str, Any] = {
        "action": decision.action,
        "reason": decision.reason,
        "intent": classification.intent,
        "confidence": classification.confidence,
    }
    if decision.action == "dm" and author_id:
        result = _send_dm(author_id, platform, decision.dm_text)
        audit["dm_sent"] = result["ok"]
        if result["ok"]:
            _record_dm_sent(business_id, post_id, author_id, intent=classification.intent)
    elif decision.action == "like_and_dm" and author_id:
        audit["liked"] = _like_comment(comment_id) if comment_id else False
        result = _send_dm(author_id, platform, decision.dm_text)
        audit["dm_sent"] = result["ok"]
        if result["ok"]:
            _record_dm_sent(business_id, post_id, author_id, intent=classification.intent)
    elif decision.action == "notify_seyma":
        audit["seyma_notified"] = _notify_seyma_complaint(business_id, payload)
    elif decision.action == "tag_spam":
        audit["tagged_spam"] = _tag_spam(comment_id) if comment_id else False
    return audit


__all__ = ["handle_comment"]
