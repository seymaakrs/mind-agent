from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.instagram_tools import get_instagram_tools
from src.tools.marketing_tools import get_marketing_tools
from src.tools.analysis_tools import get_report_tools
from src.tools.brand import fetch_brand_identity
from src.tools.sales.knowledge_tools import get_knowledge_tools
from src.tools.orchestrator_tools import (
    post_on_instagram,
    post_carousel_on_instagram,
    get_document,
    save_document,
    query_documents,
)
from src.agents.instructions import (
    MARKETING_AGENT_INSTRUCTIONS,
    BRAND_AWARE_PREFIX,
)


def create_marketing_agent(
    model: str | None = None,
    image_agent_tool: Any | None = None,
    video_agent_tool: Any | None = None,
) -> Agent[dict[str, Any]]:
    """
    Pazarlama Müdürü (Marketing Director): Sosyal medya yönetimi —
    içerik takvimi, post planlama, görsel/video brief, yayın, analiz.

    2026-05-22 yükseltmesi (Şeyma): Marketing'i "stagiyer"den "müdüre"
    yükselttik. knowledge_tools ile ürün/hedef-kitle/ses/USP'yi okur,
    Defne'ye (image) ve Toprak'a (video) brand-aware brief verir.

    Faz C: BRAND_AWARE_PREFIX talimatin basina prepend, fetch_brand_identity
    tool listesine eklenir. Marketing agent her uretim/yayim adimindan once
    brand_identity okur, voice.tone/avoid_words/preferred_words'u caption
    yazimina yansitir.

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
        fetch_brand_identity,      # Faz C: brand_identity okuma
        # 2026-05-22: Pazarlama Müdürü ürün/hedef-kitle/ses/USP'yi okur
        # (Sales Director ile aynı knowledge layer). İçerik üretiminden
        # önce get_sales_playbook ile tüm konteksti tek atışta çeker.
        *get_knowledge_tools(),
    ]

    # Add sub-agent tools if provided
    if image_agent_tool:
        tools.append(image_agent_tool)
    if video_agent_tool:
        tools.append(video_agent_tool)

    # Zernio MCP — posts_create / cross_post / boost_post / ad campaigns
    # (Late API'nin tamamlayıcısı; 14 platforma direkt yayın yapabilir).
    # Lifespan ile connect edilmis aktif server'lari al.
    from src.infra.zernio.mcp_server import get_active_mcp_servers
    mcp_servers = get_active_mcp_servers()

    return Agent(
        name="marketing",
        handoff_description=(
            "Pazarlama Müdürü (Marketing Director): içerik takvimi, "
            "post planlama, Defne'ye görsel briefi, Toprak'a video briefi, "
            "marka tonunda caption, yayın, analiz. Brand-aware: BrandIdentity "
            "+ knowledge_tools ile ürün/kitle/ses verisini kullanır."
        ),
        instructions=BRAND_AWARE_PREFIX + MARKETING_AGENT_INSTRUCTIONS,
        tools=tools,
        mcp_servers=mcp_servers,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_marketing_agent"]
