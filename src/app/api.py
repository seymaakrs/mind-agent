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
    extras: dict[str, Any] | None = Field(
        default=None, description="Optional flexible data - structure may vary per request."
    )
    context: dict[str, Any] | None = Field(
        default=None, description="Optional mutable context for the run."
    )


@app.post("/task")
async def run_task(payload: TaskRequest):
    """
    Streaming endpoint - sends heartbeat every 10s to prevent timeout.
    Final result is sent as JSON with 'type': 'result'.

    Response format (NDJSON - each line is valid JSON):
    {"type": "heartbeat", "count": 1}
    {"type": "heartbeat", "count": 2}
    ...
    {"type": "result", "success": true, "output": "...", "log_path": "..."}

    Or on error:
    {"type": "result", "success": false, "error": "..."}
    """
    async def generate():
        # Merge business_id and extras into context
        context = payload.context or {}
        if payload.business_id:
            context["business_id"] = payload.business_id
        if payload.extras:
            context["extras"] = payload.extras

        # Create task for the orchestrator
        task = asyncio.create_task(
            run_orchestrator_async(user_input=payload.task, context=context)
        )

        # Send heartbeats while waiting
        heartbeat_count = 0
        while not task.done():
            heartbeat_count += 1
            heartbeat = json.dumps({"type": "heartbeat", "count": heartbeat_count}) + "\n"
            yield heartbeat
            await asyncio.sleep(10)  # Heartbeat every 10 seconds

        # Get result
        try:
            output, log_path = await task
            result = json.dumps({
                "type": "result",
                "success": True,
                "output": output,
                "log_path": log_path
            }) + "\n"
            yield result
        except Exception as exc:
            error_detail = f"{type(exc).__name__}: {str(exc)}"
            print(f"[API ERROR] {error_detail}\n{traceback.format_exc()}")
            result = json.dumps({
                "type": "result",
                "success": False,
                "error": error_detail
            }) + "\n"
            yield result

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"}  # Disable nginx buffering
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


__all__ = ["app"]
