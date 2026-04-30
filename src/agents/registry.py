from __future__ import annotations

from typing import Any, Callable

from agents import Agent

from src.agents.image_agent import create_image_agent
from src.agents.video_agent import create_video_agent
from src.agents.marketing_agent import create_marketing_agent
from src.agents.analysis_agent import create_analysis_agent
from src.agents.orchestrator_agent import create_orchestrator_agent
from src.agents.sales import (
    create_clay_agent,
    create_ig_dm_agent,
    create_linkedin_agent,
    create_meta_lead_agent,
    create_sales_query_agent,
)

# Agent factory tipi: parametresiz cagrida yeni agent dondurur.
AgentFactory = Callable[[], Agent[dict[str, Any]]]


def create_orchestrator(
    task_logger: Any = None,
    progress_queue: Any = None,
) -> Agent[dict[str, Any]]:
    """Orchestrator agenti olusturur."""
    return create_orchestrator_agent(
        task_logger=task_logger,
        progress_queue=progress_queue,
    )


def create_image() -> Agent[dict[str, Any]]:
    """Image agenti olusturur."""
    return create_image_agent()


def create_video() -> Agent[dict[str, Any]]:
    """Video agenti olusturur."""
    return create_video_agent()


def create_marketing() -> Agent[dict[str, Any]]:
    """Marketing agenti olusturur."""
    return create_marketing_agent()


def create_analysis() -> Agent[dict[str, Any]]:
    """Analysis agenti olusturur."""
    return create_analysis_agent()


def create_sales_query() -> Agent[dict[str, Any]]:
    """Sales Query (Customer Agent — read-only) ajani olusturur."""
    return create_sales_query_agent()


def create_clay() -> Agent[dict[str, Any]]:
    """Clay (Customer Agent — yerel av) ajani olusturur."""
    return create_clay_agent()


def create_ig_dm() -> Agent[dict[str, Any]]:
    """Instagram DM (Customer Agent) ajani olusturur."""
    return create_ig_dm_agent()


def create_linkedin() -> Agent[dict[str, Any]]:
    """LinkedIn (Customer Agent) ajani olusturur."""
    return create_linkedin_agent()


def create_meta_lead() -> Agent[dict[str, Any]]:
    """Meta Lead (Customer Agent — PARK durumunda) ajani olusturur."""
    return create_meta_lead_agent()


def get_agent_registry() -> dict[str, AgentFactory]:
    """
    Tum agent olusturucularini isim bazli dondurur.
    Yeni bir agent eklendiginde buraya da ekleyin.
    """
    return {
        "orchestrator": create_orchestrator,
        "image": create_image,
        "video": create_video,
        "marketing": create_marketing,
        "analysis": create_analysis,
        # Customer Agent (kırmızı bölge)
        "sales_query": create_sales_query,
        "clay": create_clay,
        "ig_dm": create_ig_dm,
        "linkedin": create_linkedin,
        "meta_lead": create_meta_lead,
    }


__all__ = [
    "create_orchestrator",
    "create_image",
    "create_video",
    "create_marketing",
    "create_analysis",
    "create_sales_query",
    "create_clay",
    "create_ig_dm",
    "create_linkedin",
    "create_meta_lead",
    "get_agent_registry",
    "AgentFactory",
]
