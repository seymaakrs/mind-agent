"""Meta Lead Agent — Facebook + Instagram lead form processor.

Status: PARK (Session 5 decision) until Facebook App Review approval.
Currently active: autonomous campaign management via Zernio Ads API
(CTR < 1% pause, CPL > 50 freeze, etc.) — works without App Live status.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.agents.instructions.sales.meta import META_LEAD_AGENT_INSTRUCTIONS
from src.app.config import get_model_settings
from src.tools.sales.nocodb_tools import (
    create_lead,
    log_lead_message,
    notify_seyma,
    update_lead,
)
from src.tools.sales.zernio_tools import (
    get_zernio_account_analytics,
    get_zernio_campaign_metrics,
    pause_zernio_campaign,
)


def create_meta_lead_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """Meta lead agent factory.

    Combines:
    - Lead form processing (PARK — webhook akışı App Live olunca aktif)
    - Autonomous campaign management (AKTIF — Zernio Ads üzerinden)
    """
    model_settings = get_model_settings()
    return Agent(
        name="meta_lead",
        handoff_description=(
            "Facebook + Instagram reklam takipçisi. Şu an sadece otonom "
            "kampanya yönetimi aktif (CTR<%1 durdur, CPL>50 dondur). "
            "Lead webhook akışı Facebook App Review sonrasında devreye girecek."
        ),
        instructions=META_LEAD_AGENT_INSTRUCTIONS,
        tools=[
            get_zernio_campaign_metrics,
            pause_zernio_campaign,
            get_zernio_account_analytics,
            create_lead,
            update_lead,
            log_lead_message,
            notify_seyma,
        ],
        model=model or model_settings.orchestrator_model,
        tool_use_behavior="run_llm_again",
    )


__all__ = ["create_meta_lead_agent"]
