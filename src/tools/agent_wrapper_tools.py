"""
Wrapper tools for sub-agents that ensure business_id is properly passed.

These wrappers accept business_id as an explicit required parameter,
ensuring the orchestrator LLM cannot forget or fabricate it.
"""
from __future__ import annotations

from typing import Any

from agents import Agent, Runner, FunctionTool, function_tool

from src.agents.image_agent import create_image_agent
from src.agents.video_agent import create_video_agent


def create_image_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """
    Creates a wrapper tool for the image agent that requires business_id explicitly.

    The wrapper ensures business_id is passed correctly by:
    1. Requiring it as a parameter (not just in prompt text)
    2. Prepending it to the prompt in a structured way
    3. The image agent will extract and use it reliably
    """

    @function_tool(
        name_override="image_agent_tool",
        description_override=(
            "Generate images using the image agent. REQUIRED PARAMETERS: "
            "- business_id: The exact business ID from context (e.g., 'abc123') - REQUIRED! "
            "- prompt: Detailed description of the image to generate, including brand context. "
            "The image will be saved under images/{business_id}/ and tracked in Firestore."
        ),
        strict_mode=False,
    )
    async def image_agent_wrapper(
        business_id: str,
        prompt: str,
    ) -> str:
        """
        Wrapper that runs image agent with explicit business_id.

        Args:
            business_id: The business ID from Firestore (REQUIRED).
            prompt: Detailed image generation prompt with brand context.

        Returns:
            The image agent's response including path and public_url.
        """
        # Prepend business_id to ensure it's extracted correctly
        effective_prompt = f"[Business ID: {business_id}]\n\n{prompt}"

        image_agent = create_image_agent()

        result = await Runner.run(
            starting_agent=image_agent,
            input=effective_prompt,
            max_turns=3,
            hooks=hooks,
        )

        return result.final_output

    return image_agent_wrapper


def create_video_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """
    Creates a wrapper tool for the video agent that requires business_id explicitly.
    """

    @function_tool(
        name_override="video_agent_tool",
        description_override=(
            "Generate videos using the video agent. REQUIRED PARAMETERS: "
            "- business_id: The exact business ID from context (e.g., 'abc123') - REQUIRED! "
            "- prompt: Detailed description of the video to generate, including brand context. "
            "The video will be saved under videos/{business_id}/ and tracked in Firestore."
        ),
        strict_mode=False,
    )
    async def video_agent_wrapper(
        business_id: str,
        prompt: str,
    ) -> str:
        """
        Wrapper that runs video agent with explicit business_id.

        Args:
            business_id: The business ID from Firestore (REQUIRED).
            prompt: Detailed video generation prompt with brand context.

        Returns:
            The video agent's response including path and public_url.
        """
        # Prepend business_id to ensure it's extracted correctly
        effective_prompt = f"[Business ID: {business_id}]\n\n{prompt}"

        video_agent = create_video_agent()

        result = await Runner.run(
            starting_agent=video_agent,
            input=effective_prompt,
            max_turns=5,
            hooks=hooks,
        )

        return result.final_output

    return video_agent_wrapper


def create_marketing_agent_wrapper_tool(
    marketing_agent: Agent,
    hooks: Any = None,
) -> FunctionTool:
    """
    Creates a wrapper tool for the marketing agent that requires business_id explicitly.
    """

    @function_tool(
        name_override="marketing_agent_tool",
        description_override=(
            "Complete social media manager. REQUIRED PARAMETERS: "
            "- business_id: The exact business ID from context (e.g., 'abc123') - REQUIRED! "
            "- instagram_id: Late API account ID from business profile (acc_xxxxx format) - REQUIRED for posting! "
            "- prompt: What you want the marketing agent to do (plan, post, analyze). "
            "Use for: content planning, creating AND posting content, analyzing Instagram metrics. "
            "Keywords: plan, planlama, takvim, icerik, post, paylas, metrik, analiz, strateji, haftalik"
        ),
        strict_mode=False,
    )
    async def marketing_agent_wrapper(
        business_id: str,
        instagram_id: str,
        prompt: str,
    ) -> str:
        """
        Wrapper that runs marketing agent with explicit credentials.

        Args:
            business_id: The business ID from Firestore (REQUIRED).
            instagram_id: Late API account ID for Instagram posting (REQUIRED).
            prompt: What the marketing agent should do.

        Returns:
            The marketing agent's response.
        """
        # Include credentials in structured format
        effective_prompt = (
            f"[Business ID: {business_id}]\n"
            f"[Instagram ID: {instagram_id}]\n\n"
            f"{prompt}"
        )

        result = await Runner.run(
            starting_agent=marketing_agent,
            input=effective_prompt,
            max_turns=15,
            hooks=hooks,
        )

        return result.final_output

    return marketing_agent_wrapper


def create_web_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """
    Creates a wrapper tool for the web agent that optionally accepts business_id.
    """
    from src.agents.web_agent import create_web_agent

    @function_tool(
        name_override="web_agent_tool",
        description_override=(
            "Web research and analysis agent. Use for web search and website scraping. "
            "PARAMETERS: "
            "- prompt: What you want the web agent to do (search query or URL to analyze). REQUIRED! "
            "- business_id: Optional business ID if results should be associated with a business. "
            "Use for: web search, competitor research, website analysis, finding social media profiles. "
            "Keywords: ara, search, web, site analizi, rakip, competitor, website, incele, scrape"
        ),
        strict_mode=False,
    )
    async def web_agent_wrapper(
        prompt: str,
        business_id: str | None = None,
    ) -> str:
        """
        Wrapper that runs web agent with optional business_id.

        Args:
            prompt: What the web agent should do (search or analyze).
            business_id: Optional business ID for tracking.

        Returns:
            The web agent's response.
        """
        # Prepend business_id if provided
        if business_id:
            effective_prompt = f"[Business ID: {business_id}]\n\n{prompt}"
        else:
            effective_prompt = prompt

        web_agent = create_web_agent()

        result = await Runner.run(
            starting_agent=web_agent,
            input=effective_prompt,
            max_turns=5,
            hooks=hooks,
        )

        return result.final_output

    return web_agent_wrapper


def create_analysis_agent_wrapper_tool(
    analysis_agent: Agent,
    hooks: Any = None,
) -> FunctionTool:
    """
    Creates a wrapper tool for the analysis agent that requires business_id explicitly.
    """

    @function_tool(
        name_override="analysis_agent_tool",
        description_override=(
            "Business analysis agent for SWOT analysis and strategic reports. REQUIRED PARAMETERS: "
            "- business_id: The exact business ID from context (e.g., 'abc123') - REQUIRED! "
            "- prompt: What analysis you want (e.g., 'SWOT analizi yap', 'stratejik analiz'). "
            "Use for: SWOT analysis, strategic analysis, business reports. "
            "Keywords: analiz, swot, rapor, analysis, report, strateji, strategy, güçlü yönler, zayıf yönler"
        ),
        strict_mode=False,
    )
    async def analysis_agent_wrapper(
        business_id: str,
        prompt: str,
    ) -> str:
        """
        Wrapper that runs analysis agent with explicit business_id.

        Args:
            business_id: The business ID from Firestore (REQUIRED).
            prompt: What analysis to perform.

        Returns:
            The analysis agent's response including report details.
        """
        # Prepend business_id to ensure it's extracted correctly
        effective_prompt = f"[Business ID: {business_id}]\n\n{prompt}"

        result = await Runner.run(
            starting_agent=analysis_agent,
            input=effective_prompt,
            max_turns=10,  # Allow more turns for complex analysis workflows
            hooks=hooks,
        )

        return result.final_output

    return analysis_agent_wrapper


__all__ = [
    "create_image_agent_wrapper_tool",
    "create_video_agent_wrapper_tool",
    "create_marketing_agent_wrapper_tool",
    "create_web_agent_wrapper_tool",
    "create_analysis_agent_wrapper_tool",
]
