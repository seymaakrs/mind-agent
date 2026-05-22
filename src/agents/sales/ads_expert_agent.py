"""Ads Expert Agent — Zernio Ads kampanya yonetim ajani.

Distinct from ``reklam_uzmani_agent.py`` (which handles Facebook/Meta Lead
Ads form data routed into NocoDB CRM). This agent talks to Zernio's own
Ads management surface (``/v1/ads/...``) and operates as a senior
performance marketer persona.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.sales.zernio_ads_tools import get_zernio_ads_tools
from src.tools.orchestrator.business import fetch_business
from src.agents.instructions.sales import ADS_EXPERT_INSTRUCTIONS


def create_ads_expert_agent(model: str | None = None) -> Agent[dict[str, Any]]:
    """Build the Zernio Ads Expert (Reklam Uzmani v2) agent."""
    settings = get_settings()
    model_settings = get_model_settings()

    tools = [fetch_business, *get_zernio_ads_tools()]

    return Agent(
        name="ads_expert",
        handoff_description=(
            "Zernio Ads uzmani: organik post boost, kampanya yarat/durdur, "
            "butce optimizasyonu, gunluk spend/CTR/CPL raporu, custom audience yonetimi."
        ),
        instructions=ADS_EXPERT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_ads_expert_agent"]
