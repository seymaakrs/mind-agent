from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.instagram_tools import get_instagram_tools
from src.tools.marketing_tools import get_marketing_tools
from src.tools.analysis_tools import get_report_tools
from src.tools.orchestrator_tools import (
    post_on_instagram,
    post_carousel_on_instagram,
    get_document,
    save_document,
    query_documents,
)
from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS


def create_marketing_agent(
    model: str | None = None,
    image_agent_tool: Any | None = None,
    video_agent_tool: Any | None = None,
) -> Agent[dict[str, Any]]:
    """
    Marketing agent: Sosyal medya yönetimi - planlama, içerik üretimi, paylaşım, analiz.

    Args:
        model: Opsiyonel model override.
        image_agent_tool: Image agent as_tool (orchestrator'dan geçirilir).
        video_agent_tool: Video agent as_tool (orchestrator'dan geçirilir).
    """
    settings = get_settings()
    model_settings = get_model_settings()

    # Combine all tools
    tools = [
        *get_instagram_tools(),    # get_instagram_insights, get_post_analytics
        *get_marketing_tools(),    # calendar, memory, post tracking
        *get_report_tools(),       # save_instagram_report, get_reports, get_report
        post_on_instagram,         # Instagram single media posting
        post_carousel_on_instagram,  # Instagram carousel posting
        get_document,              # Firestore doc okuma (instagram_stats için)
        save_document,             # Firestore doc yazma (summary için)
        query_documents,           # Firestore query (önceki haftalar için)
    ]

    # Add sub-agent tools if provided
    if image_agent_tool:
        tools.append(image_agent_tool)
    if video_agent_tool:
        tools.append(video_agent_tool)

    return Agent(
        name="marketing",
        handoff_description="Sosyal medya yönetim agenti - planlama, içerik üretimi, paylaşım, analiz.",
        instructions=MARKETING_AGENT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_marketing_agent"]
