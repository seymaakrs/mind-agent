"""
Customer Agent — Slowdays/MindID CRM (NocoDB) uzerinde lead/pipeline okuma.

Sozlesme: docs/customer-integration-contract.md
Kapsam (Faz B/iskelet):
- Read-only tool'lar: customer_search_leads, customer_get_lead, customer_get_pipeline_summary
- Write yetenegi (notlar, seo_raporu_url) icin canAttachReports flag'i
  Faz C'de tool olarak eklenecek.

NOT: Bu agent feature flag arkasinda calisir. customerAgent.enabled=False
iken orchestrator bu agent'i tool olarak hic enjekte etmez (bkz.
src/agents/orchestrator_agent.py).
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_model_settings, get_settings
from src.agents.instructions import CUSTOMER_AGENT_INSTRUCTIONS
from src.tools.customer_tools import get_customer_tools


def create_customer_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """
    Customer agent factory. NocoDB CRM verisine erisen okuyucu agent.

    Args:
        model: Optional model override (default: orchestrator_model — bu agent
            kucuk, dusuk maliyetli model'le iyi calisir).
    """
    settings = get_settings()
    model_settings = get_model_settings()

    return Agent(
        name="customer",
        handoff_description=(
            "CRM (NocoDB) lead/pipeline sorgulayan customer agent. "
            "Lead listele, tek lead detayi, satis hunisi ozeti."
        ),
        instructions=CUSTOMER_AGENT_INSTRUCTIONS,
        tools=get_customer_tools(),
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.orchestrator_model or settings.openai_model,
    )


__all__ = ["create_customer_agent"]
