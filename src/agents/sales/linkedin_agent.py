"""LinkedIn Agent — B2B outreach hunter.

Sends connection requests + follow-up messages via Zernio LinkedIn DM API.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.agents.instructions.sales.linkedin import LINKEDIN_AGENT_INSTRUCTIONS
from src.app.config import get_model_settings
from src.tools.sales.clay_tools import generate_outreach_message
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


def create_linkedin_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """LinkedIn agent factory."""
    model_settings = get_model_settings()
    return Agent(
        name="linkedin",
        handoff_description=(
            "LinkedIn B2B outreach. Bodrum/Muğla bölgesinde karar verici "
            "profilleri (CEO, GM, Pazarlama Müdürü) bulup kişiselleştirilmiş "
            "bağlantı isteği ve mesaj dizisiyle iletişim kurar."
        ),
        instructions=LINKEDIN_AGENT_INSTRUCTIONS,
        tools=[
            send_zernio_dm,
            list_zernio_dm_threads,
            generate_outreach_message,
            create_lead,
            update_lead,
            query_leads,
            log_lead_message,
            notify_seyma,
        ],
        model=model or model_settings.orchestrator_model,
        tool_use_behavior="run_llm_again",
    )


__all__ = ["create_linkedin_agent"]
