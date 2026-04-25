from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import traceback
from typing import Annotated, Any

from agents import set_default_openai_key
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.app.capabilities import CAPABILITIES
from src.app.config import get_settings
from src.app.orchestrator_runner import run_orchestrator_async
from src.infra.thread_manager import generate_thread_id

logger = logging.getLogger(__name__)

settings = get_settings()
set_default_openai_key(settings.openai_api_key)

app = FastAPI(title="Agents Orchestrator API", version="0.1.0")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# /task endpoint MIND_AGENT_API_KEY env var ile korunur.
#
# Davranış:
#   - Env var SET DEĞİL → "legacy mode": auth bypass edilir, startup'ta uyarı
#     loglanır. Bu, deploy'dan sonra env'i set edene kadar mevcut entegrasyonların
#     bozulmamasını sağlar.
#   - Env var SET → Authorization: Bearer <key> zorunlu. Yanlış/eksik = 401.
#
# Constant-time karşılaştırma (secrets.compare_digest) timing attack'a karşı
# koruma sağlar: doğru key'in prefix'i ile yanlış bir tahmin yapan saldırgan,
# yanıt süresinden bilgi sızdıramaz.

if not os.getenv("MIND_AGENT_API_KEY", "").strip():
    logger.warning(
        "MIND_AGENT_API_KEY env var is not set. /task endpoint runs in LEGACY "
        "(unauthenticated) mode. Set the env var in production to enforce auth."
    )


def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """
    /task endpoint için kimlik doğrulama dependency'si.

    MIND_AGENT_API_KEY env var her istekte taze okunur (testlerde monkeypatch
    için, prod'da hot-reload için). Set değilse legacy mode — bypass.
    """
    expected_key = os.getenv("MIND_AGENT_API_KEY", "").strip()

    if not expected_key:
        return  # Legacy mode

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header (expected 'Bearer <key>').",
        )

    provided_key = authorization[len("Bearer "):].strip()
    if not provided_key:
        raise HTTPException(status_code=401, detail="Empty bearer token.")

    if not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid API key.")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def run_task(
    payload: TaskRequest,
    _: None = Depends(verify_api_key),
):
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


__all__ = ["app"]
