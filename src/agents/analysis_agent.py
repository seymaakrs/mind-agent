"""
Analysis Agent for business analysis reports (SWOT, SEO analysis, strategic analysis).

This agent performs SWOT analysis and SEO analysis using business profile data,
website analysis, and web research. Reports are saved to Firebase.

NOTE: Web Agent has been removed. This agent now has DIRECT access to web tools:
- web_search: Search the web
- scrape_for_seo: Detailed SEO analysis of a single website
- scrape_competitors: Batch scraping of multiple competitor websites
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.analysis_tools import get_analysis_tools
from src.tools.orchestrator_tools import fetch_business
from src.tools.web_tools import get_seo_tools
from src.agents.instructions import ANALYSIS_AGENT_INSTRUCTIONS


def create_analysis_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """
    Analysis agent for business SWOT and SEO analysis.

    This agent has DIRECT access to web tools (web_search, scrape_for_seo, scrape_competitors).
    No need for a separate web agent.

    Args:
        model: Optional model override.
    """
    settings = get_settings()
    model_settings = get_model_settings()

    # Combine all tools: business data, analysis reports, and web scraping
    tools = [
        fetch_business,
        *get_analysis_tools(),
        *get_seo_tools(),  # web_search, scrape_for_seo, scrape_competitors
    ]

    return Agent(
        name="analysis",
        handoff_description="Is analiz agenti - SWOT analizi, SEO analizi ve stratejik raporlar uretir.",
        instructions=ANALYSIS_AGENT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.analysis_agent_model or settings.openai_model,
    )


__all__ = ["create_analysis_agent"]
