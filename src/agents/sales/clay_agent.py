"""Clay (Yerel Avcı) Agent — Bodrum/Muğla local business prospecting.

Tools:
- discover_local_businesses (Clay backend via n8n bridge)
- score_business_presence (pure logic)
- generate_outreach_message (pure logic, CBO-compliant)
- create_lead, update_lead, log_lead_message, notify_seyma (NocoDB CRUD)
- query_leads (read existing leads to avoid duplicates)
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.agents.instructions.sales.clay import CLAY_AGENT_INSTRUCTIONS
from src.app.config import get_model_settings
from src.tools.sales.clay_tools import (
    discover_local_businesses,
    generate_outreach_message,
    score_business_presence,
)
from src.tools.sales.nocodb_tools import (
    create_lead,
    log_lead_message,
    notify_seyma,
    query_leads,
    update_lead,
)


def create_clay_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """Clay agent factory.

    Returns an agent with the full Clay toolchain — discovery, scoring,
    message generation, and CRM writes.
    """
    model_settings = get_model_settings()
    return Agent(
        name="clay",
        handoff_description=(
            "Bodrum/Muğla yerel işletme avcısı. Otel, restoran, cafe, butik gibi "
            "sektörlerde dijital ihtiyacı yüksek lead'leri keşfeder, skorlar, "
            "CBO standartında outreach mesajı üretir, NocoDB'ye kaydeder."
        ),
        instructions=CLAY_AGENT_INSTRUCTIONS,
        tools=[
            discover_local_businesses,
            score_business_presence,
            generate_outreach_message,
            create_lead,
            update_lead,
            log_lead_message,
            notify_seyma,
            query_leads,
        ],
        model=model or model_settings.orchestrator_model,
        tool_use_behavior="run_llm_again",
    )


__all__ = ["create_clay_agent"]
