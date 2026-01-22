from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any

from agents import set_default_openai_key
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.app.config import get_settings
from src.app.orchestrator_runner import run_orchestrator_async

settings = get_settings()
set_default_openai_key(settings.openai_api_key)

app = FastAPI(title="Agents Orchestrator API", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str = Field(..., description="User task text to run through the orchestrator.")
    business_id: str | None = Field(
        default=None, description="Business ID from Firestore 'businesses' collection."
    )
    task_id: str | None = Field(
        default=None, description="Task ID for tracking in Firebase and admin panel."
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
        # Merge business_id, task_id and extras into context
        context = payload.context or {}
        if payload.business_id:
            context["business_id"] = payload.business_id
        if payload.task_id:
            context["task_id"] = payload.task_id
        if payload.extras:
            context["extras"] = payload.extras

        # Create progress queue for streaming events
        progress_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # Create task for the orchestrator
        task = asyncio.create_task(
            run_orchestrator_async(
                user_input=payload.task,
                context=context,
                progress_queue=progress_queue,
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

        # Get result
        try:
            output, log_path = await task
            result = json.dumps({
                "type": "result",
                "success": True,
                "output": output,
                "log_path": log_path
            }, ensure_ascii=False) + "\n"
            yield result
        except Exception as exc:
            error_detail = f"{type(exc).__name__}: {str(exc)}"
            print(f"[API ERROR] {error_detail}\n{traceback.format_exc()}")
            result = json.dumps({
                "type": "result",
                "success": False,
                "error": error_detail
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


__all__ = ["app"]
