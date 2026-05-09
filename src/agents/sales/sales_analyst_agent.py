"""Sales Analyst Agent — NocoDB Leadler + Etkilesimler tablolarindan READ-ONLY
rapor uretir. Hicbir yazma yapmaz."""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.sales.reporting_tools import get_reporting_tools
from src.agents.instructions.sales import SALES_ANALYST_INSTRUCTIONS


def create_sales_analyst_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """Sales Analyst agent factory.

    Tool seti: count_leads, list_leads, lead_funnel, channel_breakdown,
    stale_leads, lead_timeline, daily_digest. Hepsi read-only.
    """
    settings = get_settings()
    model_settings = get_model_settings()

    tools = list(get_reporting_tools())

    return Agent(
        name="sales_analyst",
        handoff_description=(
            "Sales Analyst: NocoDB CRM (Leadler + Etkilesimler) uzerinden "
            "okuma yaparak rapor, sayim, liste, dagilim, trend cevabi uretir. "
            "Yazma yapmaz."
        ),
        instructions=SALES_ANALYST_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_sales_analyst_agent"]
