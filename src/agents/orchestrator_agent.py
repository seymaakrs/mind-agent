from __future__ import annotations

from datetime import datetime
import asyncio
from typing import Any

from agents import Agent

from src.app.config import (
    get_customer_agent_flags,
    get_model_settings,
    get_settings,
)
from src.app.logging_hooks import CliLoggingHooks
from src.agents.marketing_agent import create_marketing_agent
from src.agents.analysis_agent import create_analysis_agent
from src.agents.customer_agent import create_customer_agent
from src.tools.orchestrator_tools import fetch_business, get_orchestrator_tools
from src.tools.agent_wrapper_tools import (
    create_image_agent_wrapper_tool,
    create_video_agent_wrapper_tool,
    create_marketing_agent_wrapper_tool,
    create_analysis_agent_wrapper_tool,
    create_customer_agent_wrapper_tool,
)
from src.agents.instructions import build_orchestrator_instructions


def create_orchestrator_agent(
    model: str | None = None,
    task_logger: Any = None,
    progress_queue: asyncio.Queue | None = None,
) -> Agent[dict[str, Any]]:
    """
    Orchestrator agent: kullanici istegini alir, uygun alt agent/tool secip calistirir.

    Args:
        model: Optional model override.
        task_logger: Optional TaskLogger instance for Firebase logging in sub-agents.
        progress_queue: Optional asyncio.Queue for streaming progress events.
    """
    settings = get_settings()
    model_settings = get_model_settings()
    # Create hooks with task_logger for sub-agent Firebase logging AND progress streaming
    hooks = CliLoggingHooks(
        echo=False,
        task_logger=task_logger,
        progress_queue=progress_queue,
    )

    # Create wrapper tools that require business_id explicitly
    # This ensures orchestrator LLM cannot forget or fabricate business_id
    image_tool = create_image_agent_wrapper_tool(hooks=hooks)
    video_tool = create_video_agent_wrapper_tool(hooks=hooks)


    # Marketing agent with image/video tools for content generation
    marketing_agent = create_marketing_agent(
        image_agent_tool=image_tool,
        video_agent_tool=video_tool,
    )
    marketing_tool = create_marketing_agent_wrapper_tool(
        marketing_agent=marketing_agent,
        hooks=hooks,
    )

    # Analysis agent (now has direct web tools, no need for web_agent)
    analysis_agent = create_analysis_agent()
    analysis_tool = create_analysis_agent_wrapper_tool(
        analysis_agent=analysis_agent,
        hooks=hooks,
    )

    # Orchestrator tools (Firebase storage/firestore/instagram)
    orchestrator_tools = get_orchestrator_tools()

    # Customer agent tool — feature flag arkasinda. enabled=False iken bu tool
    # orchestrator'a HIC enjekte edilmez; LLM'in goremeyecegi bir araç,
    # cagrilamaz. Bu, mevcut akisslarda regresyon riskini sifir tutar.
    optional_tools: list[Any] = []
    customer_flags = get_customer_agent_flags()
    if customer_flags.enabled:
        customer_agent = create_customer_agent()
        optional_tools.append(
            create_customer_agent_wrapper_tool(
                customer_agent=customer_agent,
                hooks=hooks,
            )
        )

    # Get current date for dynamic injection
    today_date = datetime.now().strftime("%Y-%m-%d")

    return Agent(
        name="orchestrator",
        handoff_description="Alt agentlari yoneten orchestrator.",
        instructions=build_orchestrator_instructions(today_date),
        tools=[
            image_tool,
            video_tool,
            marketing_tool,
            analysis_tool,
            fetch_business,
            *orchestrator_tools,
            *optional_tools,
        ],
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.orchestrator_model or settings.openai_model,
    )


__all__ = ["create_orchestrator_agent"]
