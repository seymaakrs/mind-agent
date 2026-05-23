from __future__ import annotations

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from typing import Any

from agents import set_default_openai_key
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.app import zernio_webhook, zernio_webhook_dispatcher
from src.app.capabilities import CAPABILITIES
from src.app.config import get_settings
from src.app.sales_api import router as sales_router
from src.app.orchestrator_runner import run_orchestrator_async
from src.infra.thread_manager import generate_thread_id

settings = get_settings()
set_default_openai_key(settings.openai_api_key)

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup/shutdown hooks. MCP server'lari burada connect ediliyor
    (SDK 0.6.2 Agent(mcp_servers=...) otomatik connect etmiyor).

    NOT (2026-05-20): Langfuse instrument() cagrisi MCP streamable_http
    client'i ile anyio cakismasi yaratti (RuntimeError: aclose() already
    running). Geçici olarak devre disi — kod kalir, lifespan'dan
    cikarildi. Dogru entegrasyon ayri PR'da. Bkz. TODO.md.
    """
    from src.infra.zernio.mcp_server import start_mcp_servers, stop_mcp_servers

    await start_mcp_servers()
    try:
        yield
    finally:
        await stop_mcp_servers()


app = FastAPI(
    title="Agents Orchestrator API",
    version="0.1.0",
    lifespan=_lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sales REST API — portal Sales dashboard'i direkt cagirir (LLM yok).
app.include_router(sales_router)


class Reference(BaseModel):
    """A Firebase item (document or file) the user has selected in the frontend."""

    type: str = Field(
        ...,
        description=(
            "Item type: 'image' | 'video' | 'instagram_post' | 'report' | 'media' | 'plan'"
        ),
    )
    id: str = Field(
        ...,
        description="Firestore document path (e.g. businesses/abc/instagram_posts/xyz) or Storage file path.",
    )
    url: str | None = Field(
        default=None,
        description="Public URL for storage files. Agent can use this directly without fetching.",
    )
    label: str | None = Field(
        default=None,
        description="Optional human-readable label shown in the UI (e.g. 'Geçen haftanın görseli').",
    )


class TaskRequest(BaseModel):
    task: str = Field(..., description="User task text to run through the orchestrator.")
    business_id: str | None = Field(
        default=None, description="Business ID from Firestore 'businesses' collection."
    )
    task_id: str | None = Field(
        default=None, description="Task ID for tracking in Firebase and admin panel."
    )
    thread_id: str | None = Field(
        default=None,
        description=(
            "Conversation thread ID for multi-turn chat. "
            "Omit to start a new thread — the API will generate one and return it. "
            "Pass the value from a previous response to continue the same conversation."
        ),
    )
    references: list[Reference] | None = Field(
        default=None,
        description=(
            "Firebase items the user has selected in the UI. "
            "Injected into the agent context as a [Referenced Items] block."
        ),
    )
    extras: dict[str, Any] | None = Field(
        default=None, description="Optional flexible data - structure may vary per request."
    )
    context: dict[str, Any] | None = Field(
        default=None, description="Optional mutable context for the run."
    )


@app.post("/task")
async def run_task(payload: TaskRequest):
    """
    Streaming endpoint - sends progress events and heartbeats to prevent timeout.
    Final result is sent as JSON with 'type': 'result'.

    Response format (NDJSON - each line is valid JSON):
    {"type": "progress", "event": "agent_start", "message": "🤖 orchestrator agent başladı"}
    {"type": "progress", "event": "tool_start", "message": "🔧 fetch_business çalıştırılıyor..."}
    {"type": "progress", "event": "tool_end", "message": "✅ fetch_business tamamlandı"}
    {"type": "heartbeat"}
    {"type": "result", "success": true, "output": "...", "log_path": "..."}

    Or on error:
    {"type": "result", "success": false, "error": "..."}
    """
    async def generate():
        # Resolve thread_id — generate a new one if the client didn't provide one
        thread_id = payload.thread_id or generate_thread_id()

        # Merge business_id, task_id, extras and references into context
        context = payload.context or {}
        if payload.business_id:
            context["business_id"] = payload.business_id
        if payload.task_id:
            context["task_id"] = payload.task_id
        if payload.extras:
            context["extras"] = payload.extras
        if payload.references:
            context["references"] = [r.model_dump(exclude_none=True) for r in payload.references]

        # Create progress queue for streaming events
        progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # Create task for the orchestrator
        task = asyncio.create_task(
            run_orchestrator_async(
                user_input=payload.task,
                context=context,
                progress_queue=progress_queue,
                thread_id=thread_id,
            )
        )

        # Stream progress events and heartbeats while waiting
        while not task.done():
            try:
                # Wait for progress event with 2 second timeout
                progress = await asyncio.wait_for(
                    progress_queue.get(),
                    timeout=2.0
                )
                yield json.dumps(progress, ensure_ascii=False) + "\n"
            except asyncio.TimeoutError:
                # No progress event, send heartbeat to keep connection alive
                yield json.dumps({"type": "heartbeat"}) + "\n"

        # Drain any remaining events that were queued just before task completed
        # (race condition: last events like agent_end may be in queue when loop exits)
        while not progress_queue.empty():
            try:
                progress = progress_queue.get_nowait()
                yield json.dumps(progress, ensure_ascii=False) + "\n"
            except asyncio.QueueEmpty:
                break

        # Get result
        try:
            output, log_path = await task
            result = json.dumps({
                "type": "result",
                "success": True,
                "output": output,
                "log_path": log_path,
                "thread_id": thread_id,
            }, ensure_ascii=False) + "\n"
            yield result
        except Exception as exc:
            error_detail = f"{type(exc).__name__}: {str(exc)}"
            print(f"[API ERROR] {error_detail}\n{traceback.format_exc()}")
            result = json.dumps({
                "type": "result",
                "success": False,
                "error": error_detail,
                "thread_id": thread_id,
            }, ensure_ascii=False) + "\n"
            yield result

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "X-Accel-Buffering": "no",      # Disable nginx buffering
            "Cache-Control": "no-cache",     # Prevent caching
            "Connection": "keep-alive",      # Keep connection alive
            "Transfer-Encoding": "chunked",  # Enable chunked transfer
        }
    )


@app.get("/capabilities")
async def get_capabilities():
    """Returns the full list of agent capabilities in structured JSON.

    Intended for frontend use — display a feature overview or help page.
    Does not invoke any AI model; response is static.
    """
    return CAPABILITIES


@app.post("/zernio/webhook")
async def zernio_inbox_webhook(
    request: Request,
    x_zernio_signature: str | None = Header(default=None, alias="X-Zernio-Signature"),
):
    """Zernio Inbox webhook receiver — bypasses n8n Lead Toplama Agent.

    Verifies HMAC-SHA256 (when ZERNIO_WEBHOOK_SECRET is set), then upserts a
    Lead row + logs the inbound message into Etkilesimler. ``message.received``
    + ``direction=incoming`` events become leads; everything else is acked
    with ``skipped=true``.
    """
    raw_body = await request.body()
    ok, reason = zernio_webhook.verify_signature(raw_body, x_zernio_signature)
    if not ok:
        raise HTTPException(status_code=401, detail=f"signature: {reason}")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    event = payload.get("event")
    if event == "message.received":
        # Slowdays parity — legacy handler shape preserved.
        return zernio_webhook.handle(payload)
    return zernio_webhook_dispatcher.dispatch(payload)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Admin: Zernio observability surface
# ---------------------------------------------------------------------------
import os as _os
import time as _time


def _check_admin(x_admin_token: str | None) -> None:
    """Lightweight admin guard. Compares ``X-Admin-Token`` header against
    ``ADMIN_API_TOKEN`` env. Unset = open (dev), matches mind-agent pattern
    for ZERNIO_WEBHOOK_SECRET soft mode."""
    expected = _os.environ.get("ADMIN_API_TOKEN")
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")


def _window_stats(now_ts: float, window_sec: int) -> dict[str, Any]:
    from src.infra.zernio.base import REQUEST_LOG

    cutoff = now_ts - window_sec
    rows = [r for r in REQUEST_LOG if r.get("timestamp", 0) >= cutoff]
    n = len(rows)
    n_5xx = sum(1 for r in rows if r.get("status_class") == "5xx")
    n_429 = sum(1 for r in rows if int(r.get("status") or 0) == 429)
    lats = sorted(float(r.get("latency_ms") or 0.0) for r in rows)
    p95 = lats[max(0, min(len(lats) - 1, int(round(0.95 * (len(lats) - 1)))))] if lats else 0.0
    return {
        "calls": n,
        "5xx_rate": round((n_5xx / n) if n else 0.0, 4),
        "429_count": n_429,
        "p95_latency_ms": round(p95, 2),
    }


_LAST_ALERT_STATE: dict[str, Any] = {
    "current_alert_level": "GREEN",
    "last_alert_at": None,
    "last_alert_reason": None,
}


@app.get("/admin/zernio/status")
async def zernio_admin_status(x_admin_token: str | None = Header(default=None)):
    """Operator status — windowed stats + current alert level."""
    _check_admin(x_admin_token)
    now = _time.time()
    return {
        "last_5min": _window_stats(now, 300),
        "last_1hr": _window_stats(now, 3600),
        "last_24hr": _window_stats(now, 86400),
        **_LAST_ALERT_STATE,
    }


@app.get("/admin/zernio/recent-calls")
async def zernio_admin_recent_calls(
    limit: int = 100,
    x_admin_token: str | None = Header(default=None),
):
    """Returns the most recent ring-buffer entries (newest last)."""
    _check_admin(x_admin_token)
    from src.infra.zernio.base import REQUEST_LOG

    limit = max(1, min(limit, 1000))
    rows = list(REQUEST_LOG)[-limit:]
    return {"count": len(rows), "calls": rows}


__all__ = ["app"]
