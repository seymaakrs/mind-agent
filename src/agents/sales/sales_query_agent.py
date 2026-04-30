"""Sales Query Agent — read-only NL interface to the CRM.

Invoked from the mind-id chat panel. Şeyma asks "kaç sıcak lead var?" and the
agent translates the question to NocoDB queries via tools, then summarizes.

Read-only by construction:
- Imports ONLY ``get_sales_query_tools()`` (no create/update/notify)
- Cannot mutate state even if asked

Wiring:
- ``create_sales_query_agent`` returns an Agent instance.
- It can be wrapped via ``agent_wrapper_tools.create_sales_query_agent_wrapper_tool``
  and registered to the orchestrator (Faz 7).
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.agents.instructions.sales import SALES_QUERY_AGENT_INSTRUCTIONS
from src.app.config import get_model_settings
from src.tools.sales import get_sales_query_tools


def create_sales_query_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """Sales Query Agent — read-only NocoDB query interface.

    Args:
        model: Optional model override.

    Returns:
        Agent instance ready to handle natural-language sales queries.
    """
    model_settings = get_model_settings()
    return Agent(
        name="sales_query",
        handoff_description=(
            "CRM'deki satış verilerine doğal dilde sorgu yapan read-only agent. "
            "'Kaç sıcak lead var?', 'Pipeline ne kadar?', 'Hangi kanal en iyi?' "
            "tarzı soruları yanıtlar. Veri değiştirmez."
        ),
        instructions=SALES_QUERY_AGENT_INSTRUCTIONS,
        tools=get_sales_query_tools(),
        model=model or model_settings.orchestrator_model,
        tool_use_behavior="run_llm_again",
    )


__all__ = ["create_sales_query_agent"]
