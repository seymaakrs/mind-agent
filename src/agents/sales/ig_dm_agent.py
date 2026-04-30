"""Instagram DM Agent — Zernio Inbox webhook'undan tetiklenir.

Inbound DM → niyeti anla → otomatik yanıt veya Şeyma'ya escalate.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.agents.instructions.sales.ig_dm import IG_DM_AGENT_INSTRUCTIONS
from src.app.config import get_model_settings
from src.tools.sales.nocodb_tools import (
    create_lead,
    log_lead_message,
    notify_seyma,
    query_leads,
    update_lead,
)
from src.tools.sales.zernio_tools import (
    list_zernio_dm_threads,
    send_zernio_dm,
)


def create_ig_dm_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """Instagram DM agent factory."""
    model_settings = get_model_settings()
    return Agent(
        name="ig_dm",
        handoff_description=(
            "Instagram DM otomasyonu. Slowdays Bodrum'a gelen DM'leri yorumlar, "
            "CBO-uyumlu otomatik yanıt verir, sıcak lead'leri Şeyma'ya iletir."
        ),
        instructions=IG_DM_AGENT_INSTRUCTIONS,
        tools=[
            send_zernio_dm,
            list_zernio_dm_threads,
            create_lead,
            update_lead,
            query_leads,
            log_lead_message,
            notify_seyma,
        ],
        model=model or model_settings.orchestrator_model,
        tool_use_behavior="run_llm_again",
    )


__all__ = ["create_ig_dm_agent"]
