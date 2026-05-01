from __future__ import annotations

import asyncio
import json
from typing import Any

from agents import Runner, set_default_openai_key

from src.agents.registry import create_orchestrator
from src.app.config import get_settings
from src.app.logging_hooks import CliLoggingHooks
from src.infra.task_logger import TaskLogger
from src.infra.thread_manager import ThreadManager

_settings = get_settings()
set_default_openai_key(_settings.openai_api_key)


def _is_lead_query(text: str) -> bool:
    """Detect if a user message is a lead/CRM query that must route to meta_agent_tool."""
    import re
    # Match 'lead' as a whole word or with common Turkish suffixes
    return bool(re.search(r"\blead(s|ler|leri|lerin|lerden|lere)?\b", text, re.IGNORECASE))


def _build_effective_input(user_input: str, ctx: dict[str, Any]) -> str:
    """Build effective input with business_id, references and extras injected."""
    business_id = ctx.get("business_id")
    references = ctx.get("references")
    extras = ctx.get("extras")

    effective_input = user_input
    # Pre-router: lead/CRM queries get a hard directive injected into the user message
    # so the orchestrator LLM cannot ignore the routing rule.
    if _is_lead_query(user_input):
        effective_input = (
            "[ROUTING DIRECTIVE — MANDATORY]\n"
            "This message is a lead/CRM query. You MUST call meta_agent_tool directly. "
            "DO NOT call query_documents, get_document, fetch_business, analysis_agent_tool, "
            "or marketing_agent_tool. meta_agent_tool is the ONLY correct tool for this request. "
            "Pass the user's question and business_id to meta_agent_tool, then return its result.\n"
            "[/ROUTING DIRECTIVE]\n\n"
            f"{effective_input}"
        )
    if business_id:
        effective_input = f"[Business ID: {business_id}]\n{effective_input}"
    if references:
        lines = ["[Referenced Items]"]
        for ref in references:
            line = f"• {ref['type']} | ID: {ref['id']}"
            if ref.get("url"):
                line += f"\n  URL: {ref['url']}"
            if ref.get("label"):
                line += f"\n  Label: {ref['label']}"
            lines.append(line)
        effective_input = f"{effective_input}\n\n" + "\n".join(lines)
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
    user_input: str,
    context: dict[str, Any] | None = None,
    progress_queue: asyncio.Queue | None = None,
    thread_id: str | None = None,
) -> tuple[str, str | None]:
    """Run orchestrator asynchronously and return (output, log_path)."""
    ctx = context or {}
    business_id = ctx.get("business_id")

    # Build the text for this turn (business_id prefix always injected)
    new_message_text = _build_effective_input(user_input, ctx)

    # Multi-turn: load existing history and build the correct Runner input type.
    # - history exists  → list (history + new user message)
    # - no history yet  → str  (same as single-turn, SDK wraps it automatically)
    # - no business_id  → str  (can't persist without a Firestore path)
    runner_input: str | list[dict[str, Any]]
    if thread_id and business_id:
        history = ThreadManager().load(business_id, thread_id)
        if history:
            runner_input = history + [{"role": "user", "content": new_message_text}]
        else:
            runner_input = new_message_text
    else:
        runner_input = new_message_text

    # Firebase task logger
    task_id = ctx.get("task_id")
    task_logger = TaskLogger(business_id=business_id, task_id=task_id)
    task_logger.start(user_input)

    # Create orchestrator with task_logger for sub-agent Firebase logging
    orchestrator = create_orchestrator(
        task_logger=task_logger,
        progress_queue=progress_queue,
    )

    hooks = CliLoggingHooks(
        echo=False,
        task_logger=task_logger,
        progress_queue=progress_queue,
    )
    hooks.log_task(user_input)

    try:
        result = await Runner.run(
            starting_agent=orchestrator,
            input=runner_input,
            context=ctx,
            hooks=hooks,
        )
        task_logger.complete()

        # Multi-turn: persist full conversation history after a successful run.
        # Skipped if no thread_id or no business_id (single-turn mode).
        if thread_id and business_id:
            ThreadManager().save(business_id, thread_id, result.to_input_list())

        return result.final_output, hooks.log_path
    except Exception as exc:
        task_logger.complete(error=str(exc))
        raise
    finally:
        hooks.close()


__all__ = ["run_orchestrator", "run_orchestrator_async", "CliLoggingHooks"]
