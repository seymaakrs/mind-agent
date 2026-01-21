from __future__ import annotations

from typing import Any, Callable

from agents import Agent

from src.agents.image_agent import create_image_agent
from src.agents.video_agent import create_video_agent
from src.agents.marketing_agent import create_marketing_agent
from src.agents.orchestrator_agent import create_orchestrator_agent

# Agent factory tipi: parametresiz cagrida yeni agent dondurur.
AgentFactory = Callable[[], Agent[dict[str, Any]]]


def create_orchestrator(task_logger: Any = None) -> Agent[dict[str, Any]]:
    """Orchestrator agenti olusturur."""
    return create_orchestrator_agent(task_logger=task_logger)


def create_image() -> Agent[dict[str, Any]]:
    """Image agenti olusturur."""
    return create_image_agent()


def create_video() -> Agent[dict[str, Any]]:
    """Video agenti olusturur."""
    return create_video_agent()


def create_marketing() -> Agent[dict[str, Any]]:
    """Marketing agenti olusturur."""
    return create_marketing_agent()


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
    }


__all__ = [
    "create_orchestrator",
    "create_image",
    "create_video",
    "create_marketing",
    "get_agent_registry",
    "AgentFactory",
]
