from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings, get_agent_instructions
from src.tools.video_tools import get_video_tools
from src.agents.instructions import VIDEO_AGENT_CORE_INSTRUCTIONS, DEFAULT_VIDEO_PERSONA


def create_video_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """
    Video uretimi icin prompt engineering yapan ve generate_video tool'unu kullanan agent.

    Firebase'den persona ve prompt field override'lari okunur.
    Config yoksa default degerler kullanilir.

    Args:
        model: Opsiyonel model override. Bos birakilirsa ortam ayari kullanilir.
    """
    settings = get_settings()
    model_settings = get_model_settings()
    config = get_agent_instructions("video_agent")

    persona = config.persona or DEFAULT_VIDEO_PERSONA
    instructions = VIDEO_AGENT_CORE_INSTRUCTIONS.replace("{persona}", persona)

    return Agent(
        name="video",
        handoff_description="Video olusturma alt agenti - cinematic prompt engineering yapar.",
        instructions=instructions,
        tools=get_video_tools(config),
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.video_agent_model or settings.openai_model,
    )


__all__ = ["create_video_agent"]
