"""Qualifier Agent — Faz 5: ham lead'leri ICP fit'e göre niteleyip qualified flag'ler.

Mail kapısının (qualified + source + asama) ilk koşulunu bu agent açar. ICP fit
çekirdek mantığı `src/tools/sales/icp.py` içinde (deterministik); nihai kararı
LLM verir.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.sales.nocodb_tools import (
    get_lead,
    query_leads,
    mark_lead_qualified,
    notify_seyma,
)
from src.agents.instructions.sales import QUALIFIER_INSTRUCTIONS


def create_qualifier_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """
    Qualifier Agent: gelen lead'leri ICP'ye (sektör + konum + sinyaller) göre
    değerlendirir, qualified=true/false flag'ler ve mail kapısı açıksa Seyma'ya
    bildirir.

    Args:
        model: Opsiyonel model override.
    """
    settings = get_settings()
    model_settings = get_model_settings()

    tools = [get_lead, query_leads, mark_lead_qualified, notify_seyma]

    return Agent(
        name="qualifier",
        handoff_description=(
            "Qualifier Agent: ham lead'leri ICP fit'e göre niteler, "
            "qualified=true/false flag'ler, mail kapısı açıksa Seyma'ya bildirir."
        ),
        instructions=QUALIFIER_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_qualifier_agent"]
