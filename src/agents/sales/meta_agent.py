"""Meta Reklam Agent - Facebook Lead Ads form'larindan gelen leadleri NocoDB'ye yazar."""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.sales.nocodb_tools import get_nocodb_tools
from src.agents.instructions.sales import META_AGENT_INSTRUCTIONS


def create_meta_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """
    Meta Reklam Agent: Facebook Lead Ads form trigger'indan gelen leadleri
    NocoDB CRM'e yazar, lead skoru hesaplar, sicak leadleri Seyma'ya bildirir.

    Args:
        model: Opsiyonel model override.
    """
    settings = get_settings()
    model_settings = get_model_settings()

    tools = list(get_nocodb_tools())

    return Agent(
        name="meta",
        handoff_description=(
            "Meta (Facebook/Instagram) Lead Ads agent: gelen lead form verisini "
            "NocoDB CRM'e yazar, skor hesaplar, sicak leadleri Seyma'ya bildirir."
        ),
        instructions=META_AGENT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_meta_agent"]
