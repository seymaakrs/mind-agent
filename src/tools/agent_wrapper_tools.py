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
            "- late_profile_id: Late profile ID (raw ObjectId) from business profile - REQUIRED for analytics! "
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
        late_profile_id: str | None = None,
    ) -> str:
        """
        Wrapper that runs marketing agent with explicit credentials.

        Args:
            business_id: The business ID from Firestore (REQUIRED).
            instagram_id: Late API account ID for Instagram posting (REQUIRED).
            late_profile_id: Late profile ID for Instagram analytics (REQUIRED for analytics).
            prompt: What the marketing agent should do.

        Returns:
            The marketing agent's response.
        """
        # Include credentials in structured format
        effective_prompt = (
            f"[Business ID: {business_id}]\n"
            f"[Instagram ID: {instagram_id}]\n"
            f"[Late Profile ID: {late_profile_id or 'NOT_PROVIDED'}]\n\n"
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
            "Business analysis and research agent. Handles SWOT analysis, SEO analysis, "
            "AND general research/custom reports. REQUIRED PARAMETERS: "
            "- business_id: The exact business ID from context (e.g., 'abc123') - REQUIRED! "
            "- prompt: What you want (analysis, research, report). "
            "IMPORTANT: For general research or custom reports (NOT SWOT/SEO), "
            "explicitly say 'özel rapor' or 'custom report' in the prompt so the agent uses save_custom_report. "
            "Use for: SWOT analysis, SEO analysis, web research, trend reports, technology research, custom reports. "
            "Keywords: analiz, swot, seo, rapor, araştır, araştırma, research, report, trend, haber, inceleme"
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


# ---------------------------------------------------------------------------
# Sales (Customer Agent) wrapper tools — Mind-Agent SDK Köprüsü
#
# These wire each sales sub-agent (clay, ig_dm, linkedin, meta_lead, query)
# into the main orchestrator. The orchestrator picks the right sub-agent
# based on the keywords in each tool's description.
# ---------------------------------------------------------------------------


def create_sales_query_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """Read-only natural-language query interface to the CRM."""
    from src.agents.sales import create_sales_query_agent

    @function_tool(
        name_override="sales_query_agent_tool",
        description_override=(
            "Satış / lead / pipeline / CRM verileri hakkında SORU SORMAK için. "
            "Read-only — veri DEĞİŞTİRMEZ. "
            "Keywords: kaç sıcak lead, pipeline, CAC, CPL, funnel, "
            "hangi kanal, satış raporu, hot leads, agent health, "
            "otonom karar logları."
        ),
        strict_mode=False,
    )
    async def sales_query_wrapper(prompt: str) -> str:
        agent = create_sales_query_agent()
        result = await Runner.run(
            starting_agent=agent,
            input=prompt,
            max_turns=8,
            hooks=hooks,
        )
        return result.final_output

    return sales_query_wrapper


def create_clay_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """Bodrum/Muğla yerel işletme avı."""
    from src.agents.sales import create_clay_agent

    @function_tool(
        name_override="clay_agent_tool",
        description_override=(
            "Bodrum / Muğla yerel işletmeleri keşfeder, skorlar ve outreach mesajı "
            "hazırlar. Otel, restoran, cafe, butik, perakende, turizm, e-ticaret. "
            "Keywords: yerel işletme, bodrum tara, otel listesi, restoran ara, "
            "lead skor, outreach mesajı, soğuk e-posta, prospecting, b2b yerel."
        ),
        strict_mode=False,
    )
    async def clay_wrapper(prompt: str) -> str:
        agent = create_clay_agent()
        result = await Runner.run(
            starting_agent=agent, input=prompt, max_turns=15, hooks=hooks
        )
        return result.final_output

    return clay_wrapper


def create_ig_dm_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """Instagram DM otomasyonu (Zernio Inbox webhook'undan tetiklenir)."""
    from src.agents.sales import create_ig_dm_agent

    @function_tool(
        name_override="ig_dm_agent_tool",
        description_override=(
            "Instagram DM yönetimi. Gelen DM'leri yorumlar, CBO-uyumlu "
            "otomatik yanıt verir, sıcak lead'leri Şeyma'ya iletir. "
            "Keywords: instagram dm, ig mesaj, gelen mesaj, otomatik yanıt, "
            "instagram lead."
        ),
        strict_mode=False,
    )
    async def ig_dm_wrapper(prompt: str) -> str:
        agent = create_ig_dm_agent()
        result = await Runner.run(
            starting_agent=agent, input=prompt, max_turns=10, hooks=hooks
        )
        return result.final_output

    return ig_dm_wrapper


def create_linkedin_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """LinkedIn outreach (Zernio LinkedIn DM)."""
    from src.agents.sales import create_linkedin_agent

    @function_tool(
        name_override="linkedin_agent_tool",
        description_override=(
            "LinkedIn B2B outreach. Karar verici profillere (CEO, GM, Pazarlama "
            "Müdürü) bağlantı isteği + kişiselleştirilmiş mesaj dizisi gönderir. "
            "Keywords: linkedin outreach, profesyonel ağ, bağlantı isteği, "
            "linkedin mesaj, b2b satış, karar verici."
        ),
        strict_mode=False,
    )
    async def linkedin_wrapper(prompt: str) -> str:
        agent = create_linkedin_agent()
        result = await Runner.run(
            starting_agent=agent, input=prompt, max_turns=10, hooks=hooks
        )
        return result.final_output

    return linkedin_wrapper


def create_meta_lead_agent_wrapper_tool(hooks: Any = None) -> FunctionTool:
    """Meta (Facebook + Instagram) reklam ve lead form takibi."""
    from src.agents.sales import create_meta_lead_agent

    @function_tool(
        name_override="meta_lead_agent_tool",
        description_override=(
            "Facebook + Instagram reklam takibi. Otonom kampanya yönetimi "
            "(CTR<%1 durdur, CPL>50 dondur). Lead form akışı şu an PARK "
            "(FB App Review beklemede). "
            "Keywords: meta reklam, facebook ads, instagram reklam, kampanya, "
            "ctr, cpl, lead form, reklam metriği, facebook lead."
        ),
        strict_mode=False,
    )
    async def meta_lead_wrapper(prompt: str) -> str:
        agent = create_meta_lead_agent()
        result = await Runner.run(
            starting_agent=agent, input=prompt, max_turns=10, hooks=hooks
        )
        return result.final_output

    return meta_lead_wrapper


__all__ = [
    "create_image_agent_wrapper_tool",
    "create_video_agent_wrapper_tool",
    "create_marketing_agent_wrapper_tool",
    "create_analysis_agent_wrapper_tool",
    "create_sales_query_agent_wrapper_tool",
    "create_clay_agent_wrapper_tool",
    "create_ig_dm_agent_wrapper_tool",
    "create_linkedin_agent_wrapper_tool",
    "create_meta_lead_agent_wrapper_tool",
]
