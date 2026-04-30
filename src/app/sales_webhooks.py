"""FastAPI webhook receivers for the Customer Agent (sales) flow.

Two endpoints:

POST /sales/webhook/zernio
    Generic Zernio Inbox webhook (DM events for IG / FB / LinkedIn / WhatsApp).
    The body is forwarded to the orchestrator with the relevant sales agent
    routed based on the platform field.

POST /sales/webhook/meta-lead
    Facebook Lead Ads webhook (PARK status until App Review approves).
    Same routing pattern, target agent = ``meta_lead_agent``.

Both endpoints:
- Verify HMAC-SHA256 signature against ``ZERNIO_WEBHOOK_SECRET`` /
  ``META_WEBHOOK_SECRET`` env vars (raw body — verify before parsing!)
- Idempotency: Zernio sends ``X-Zernio-Delivery-Id`` header; we de-dupe in
  process memory (5-min TTL) — for production, swap to NocoDB or Redis.
- Return 200 quickly (Zernio retries on non-2xx). Long-running orchestrator
  invocation runs in BackgroundTasks.

Wiring:
- Mounted onto the main FastAPI app via ``include_router``. See ``api.py``.
- Disabled (no routes registered) when ``SALES_AGENTS_ENABLED=False``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from src.infra.zernio_client import ZernioClient

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sales/webhook", tags=["sales-webhooks"])


# ---------------------------------------------------------------------------
# Idempotency (in-process — replace with Redis/NocoDB for multi-instance prod)
# ---------------------------------------------------------------------------


_seen: dict[str, float] = {}
_SEEN_TTL_SECONDS = 300  # 5 min


def _is_duplicate(key: str) -> bool:
    """Returns True if `key` was seen within TTL. Records this key as seen."""
    now = time.time()
    # Lazy purge
    if len(_seen) > 1000:
        cutoff = now - _SEEN_TTL_SECONDS
        for k in [k for k, t in _seen.items() if t < cutoff]:
            _seen.pop(k, None)
    last = _seen.get(key)
    if last is not None and (now - last) < _SEEN_TTL_SECONDS:
        return True
    _seen[key] = now
    return False


def _reset_idempotency_cache() -> None:
    """Test helper — clear the in-memory idempotency record."""
    _seen.clear()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def _verify_or_raise(
    raw_body: bytes,
    signature_header: str | None,
    env_var_name: str,
) -> None:
    """Common HMAC-SHA256 check. Raises 401 if signature invalid.

    If the secret env var is unset we bypass verification ONLY when running in
    a test/dev profile (DRY_RUN=true). In production we hard-fail to avoid
    silent insecure deployments.
    """
    secret = os.getenv(env_var_name, "")
    dry_run = os.getenv("DRY_RUN", "").lower() in ("true", "1", "yes")
    if not secret:
        if dry_run:
            log.warning(
                "[%s] not set; bypassing signature verification (DRY_RUN=true).",
                env_var_name,
            )
            return
        raise HTTPException(
            status_code=503,
            detail=f"Webhook secret missing ({env_var_name}); refusing to process.",
        )
    if not ZernioClient.verify_webhook_signature(
        raw_body, signature_header, secret
    ):
        raise HTTPException(status_code=401, detail="Invalid signature.")


# ---------------------------------------------------------------------------
# Background dispatch — pushes to orchestrator without blocking the response
# ---------------------------------------------------------------------------


def _format_zernio_dm_task(payload: dict[str, Any]) -> str:
    """Convert a Zernio message.received payload into a Türkçe orchestrator task."""
    data = payload.get("data") or payload
    platform = str(data.get("platform") or "instagram").lower()
    sender = data.get("sender_id") or data.get("sender", {}).get("id") or "?"
    text = data.get("text") or data.get("message") or "(boş mesaj)"
    thread_id = data.get("thread_id") or "?"
    account_id = data.get("account_id") or "?"

    routing_hint = (
        "instagram dm"
        if platform == "instagram"
        else "facebook dm"
        if platform == "facebook"
        else "linkedin mesaj"
        if platform == "linkedin"
        else "whatsapp mesaj"
        if platform == "whatsapp"
        else f"{platform} dm"
    )

    return (
        f"[Sales webhook] Yeni {routing_hint} geldi. "
        f"Platform: {platform}, account: {account_id}, sender: {sender}, "
        f"thread: {thread_id}.\n"
        f"Mesaj içeriği:\n{text}\n\n"
        f"Lütfen ilgili sales sub-agent'ına yönlendir, "
        f"NocoDB'ye logla ve gerekirse otomatik yanıt ver."
    )


def _format_meta_lead_task(payload: dict[str, Any]) -> str:
    """Convert FB Lead Ads webhook into a Türkçe orchestrator task."""
    entry = (payload.get("entry") or [{}])[0]
    changes = entry.get("changes") or [{}]
    leadgen = (changes[0] or {}).get("value") or {}
    leadgen_id = leadgen.get("leadgen_id") or "?"
    page_id = leadgen.get("page_id") or "?"
    form_id = leadgen.get("form_id") or "?"
    return (
        f"[Sales webhook] Yeni Facebook Lead Ads form gönderimi. "
        f"leadgen_id={leadgen_id}, page_id={page_id}, form_id={form_id}.\n"
        f"meta_lead_agent'a yönlendir: lead detaylarını çek, skor hesapla, "
        f"NocoDB'ye yaz ve skor 8+ ise notify_seyma çağır."
    )


async def _dispatch_to_orchestrator(task_text: str, business_id: str) -> None:
    """Run the orchestrator in the background. Errors are logged, not surfaced —
    the webhook caller already received 200 OK."""
    try:
        # Imported here to avoid loading at module import time (Firebase init lag).
        from src.app.orchestrator_runner import run_orchestrator_async

        await run_orchestrator_async(
            task=task_text,
            business_id=business_id or "global",
            task_id=f"webhook-{int(time.time() * 1000)}",
            extras={"source": "sales_webhook"},
        )
    except Exception:  # noqa: BLE001
        log.exception("Sales webhook dispatch failed")


def _schedule_dispatch(
    background_tasks: BackgroundTasks, task_text: str, business_id: str
) -> None:
    """FastAPI BackgroundTasks expects a sync callable; wrap the coroutine."""

    def _run() -> None:
        try:
            asyncio.run(_dispatch_to_orchestrator(task_text, business_id))
        except RuntimeError:
            # Loop is already running (rare in BackgroundTasks). Fall back to
            # creating a task on the running loop.
            loop = asyncio.get_event_loop()
            loop.create_task(_dispatch_to_orchestrator(task_text, business_id))

    background_tasks.add_task(_run)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/zernio")
async def zernio_inbox_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_zernio_signature: str | None = Header(default=None),
    x_zernio_delivery_id: str | None = Header(default=None),
) -> dict[str, Any]:
    """Receive Zernio Inbox events (message.received, message.delivered, ...)."""
    raw = await request.body()
    _verify_or_raise(raw, x_zernio_signature, "ZERNIO_WEBHOOK_SECRET")

    if x_zernio_delivery_id and _is_duplicate(f"zernio:{x_zernio_delivery_id}"):
        return {"ok": True, "deduped": True}

    try:
        import json

        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = str(payload.get("event") or payload.get("type") or "")
    if event not in ("message.received", "comment.received"):
        # We accept other events (delivered, read receipts) but don't dispatch
        # to the orchestrator for them. Log + ack.
        log.info("Zernio webhook accepted (no dispatch): event=%s", event)
        return {"ok": True, "dispatched": False, "event": event}

    task_text = _format_zernio_dm_task(payload)
    _schedule_dispatch(background_tasks, task_text, business_id="global")
    return {"ok": True, "dispatched": True, "event": event}


@router.post("/meta-lead")
async def meta_lead_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, Any]:
    """Receive Facebook Lead Ads ``leadgen`` webhooks (PARK until App Live)."""
    raw = await request.body()
    _verify_or_raise(raw, x_hub_signature_256, "META_WEBHOOK_SECRET")

    try:
        import json

        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Idempotency on the first leadgen_id we see.
    entry = (payload.get("entry") or [{}])[0]
    changes = entry.get("changes") or [{}]
    leadgen = (changes[0] or {}).get("value") or {}
    leadgen_id = str(leadgen.get("leadgen_id") or "")
    if leadgen_id and _is_duplicate(f"meta-lead:{leadgen_id}"):
        return {"ok": True, "deduped": True}

    task_text = _format_meta_lead_task(payload)
    _schedule_dispatch(background_tasks, task_text, business_id="global")
    return {"ok": True, "dispatched": True, "leadgen_id": leadgen_id}


# Verification GET for FB webhook subscription challenge (App config requires it).
@router.get("/meta-lead")
async def meta_lead_verify(request: Request) -> Any:
    """Facebook webhook subscription verification (hub.challenge)."""
    qs = request.query_params
    mode = qs.get("hub.mode")
    token = qs.get("hub.verify_token")
    challenge = qs.get("hub.challenge")
    expected = os.getenv("META_VERIFY_TOKEN", "")
    if mode == "subscribe" and token and expected and token == expected:
        # Plain text challenge expected by FB
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


__all__ = ["router"]
