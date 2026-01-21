from __future__ import annotations

import json
from typing import Any

from agents import Runner, set_default_openai_key

from src.agents.registry import create_orchestrator
from src.app.config import get_settings
from src.app.logging_hooks import CliLoggingHooks
from src.infra.task_logger import TaskLogger

_settings = get_settings()
set_default_openai_key(_settings.openai_api_key)


def _build_effective_input(user_input: str, ctx: dict[str, Any]) -> str:
    """Build effective input with business_id and extras injected."""
    business_id = ctx.get("business_id")
    extras = ctx.get("extras")

    effective_input = user_input
    if business_id:
        effective_input = f"[Business ID: {business_id}]\n{effective_input}"
    if extras:
        extras_json = json.dumps(extras, ensure_ascii=False, indent=2)
        effective_input = f"{effective_input}\n\n[Extras]\n{extras_json}"

    return effective_input


def run_orchestrator(user_input: str, context: dict[str, Any] | None = None) -> str:
    """
    Dis dunya icin tek cikis noktasi: Orchestrator agenti calistirir ve son ciktiyi dondurur.

    Args:
        user_input: Kullanicidan gelen metin.
        context: Opsiyonel calisma baglami (mutable dict beklenir).
    """
    ctx = context or {}
    business_id = ctx.get("business_id")
    effective_input = _build_effective_input(user_input, ctx)

    # Firebase task logger
    task_id = ctx.get("task_id")
    task_logger = TaskLogger(business_id=business_id, task_id=task_id)
    task_logger.start(user_input)

    # Create orchestrator with task_logger for sub-agent Firebase logging
    orchestrator = create_orchestrator(task_logger=task_logger)

    hooks = CliLoggingHooks(task_logger=task_logger)
    hooks.log_task(user_input)

    try:
        result = Runner.run_sync(
            starting_agent=orchestrator,
            input=effective_input,
            context=ctx,
            hooks=hooks,
        )
        task_logger.complete()
        return result.final_output
    except Exception as exc:
        task_logger.complete(error=str(exc))
        raise
    finally:
        hooks.close()


async def run_orchestrator_async(
    user_input: str, context: dict[str, Any] | None = None
) -> tuple[str, str | None]:
    """Run orchestrator asynchronously and return (output, log_path)."""
    ctx = context or {}
    business_id = ctx.get("business_id")
    effective_input = _build_effective_input(user_input, ctx)

    # Firebase task logger
    task_id = ctx.get("task_id")
    task_logger = TaskLogger(business_id=business_id, task_id=task_id)
    task_logger.start(user_input)

    # Create orchestrator with task_logger for sub-agent Firebase logging
    orchestrator = create_orchestrator(task_logger=task_logger)

    hooks = CliLoggingHooks(echo=False, task_logger=task_logger)
    hooks.log_task(user_input)

    try:
        result = await Runner.run(
            starting_agent=orchestrator,
            input=effective_input,
            context=ctx,
            hooks=hooks,
        )
        task_logger.complete()
        return result.final_output, hooks.log_path
    except Exception as exc:
        task_logger.complete(error=str(exc))
        raise
    finally:
        hooks.close()


__all__ = ["run_orchestrator", "run_orchestrator_async", "CliLoggingHooks"]
