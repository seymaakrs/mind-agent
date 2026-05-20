from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings, get_agent_instructions
from src.tools.image_tools import get_image_tools
from src.tools.brand import fetch_brand_identity
from src.agents.instructions import (
    IMAGE_AGENT_CORE_INSTRUCTIONS,
    DEFAULT_IMAGE_PERSONA,
    BRAND_AWARE_PREFIX,
)


def create_image_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """
    Gorsel uretimi icin prompt engineering yapan ve generate_image tool'unu kullanan agent.

    Firebase'den persona ve prompt field override'lari okunur.
    Config yoksa default degerler kullanilir.

    Faz C: BRAND_AWARE_PREFIX talimatin basina prepend, fetch_brand_identity
    tool listesine eklenir. Agent ilk adimda Firestore'dan brand_identity
    okur ve gorsel brief'inin basina enjekte eder.

    Args:
        model: Opsiyonel model override. Bos birakilirsa ortam ayari kullanilir.
    """
    settings = get_settings()
    model_settings = get_model_settings()
    config = get_agent_instructions("image_agent")

    persona = config.persona or DEFAULT_IMAGE_PERSONA
    instructions = BRAND_AWARE_PREFIX + IMAGE_AGENT_CORE_INSTRUCTIONS.replace(
        "{persona}", persona
    )

    tools = list(get_image_tools(config))
    tools.append(fetch_brand_identity)

    return Agent(
        name="image",
        handoff_description="Gorsel olusturma alt agenti - prompt engineering yapar.",
        instructions=instructions,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.image_agent_model or settings.openai_model,
    )


__all__ = ["create_image_agent"]
