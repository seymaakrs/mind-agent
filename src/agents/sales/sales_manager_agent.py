"""Sales Manager (Satis Muduru) — alt birim (Avci, DM Yanitlayici) yoneten,
yan birim (Reklam Uzmani) ile koordine olan agent.

Eski adi 'Sales Analyst' idi (sadece okuma, rapor). Bu yeni versiyon ayni
read tool'larini koruyor ama persona yonetici — aksiyon onerici, oncelik
verici, koordine eden. Yazma yetkisi henuz YOK; TODO listesinde:

- TODO: outreach_pause / outreach_resume tool'lari
- TODO: auto_reply_template_update
- TODO: lead_reassign
- TODO: meta_agent_tool dogrudan emrinde (yatay iletisim)
- TODO: brand_identity okuma (BRAND_AWARE_PREFIX)
- TODO: sales memory (get_sales_memory / update_sales_memory)
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.tools.sales.reporting_tools import get_reporting_tools
from src.tools.brand import fetch_brand_identity
from src.agents.instructions.sales import SALES_MANAGER_INSTRUCTIONS
from src.agents.instructions.brand_aware import BRAND_AWARE_PREFIX


def create_sales_manager_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """Sales Manager agent factory.

    Tool seti (su an okuma): count_leads, list_leads, lead_funnel,
    channel_breakdown, stale_leads, lead_timeline, daily_digest,
    outreach_status, auto_reply_status, outreach_health.

    Args:
        model: Opsiyonel override. Default gpt-4o-mini (Zernio MCP'siz
            calistigi icin daha yuksek modele cikilabilir, ancak rapor
            anlatimi icin mini yeterli + ucuz).
    """
    tools = list(get_reporting_tools()) + [fetch_brand_identity]

    # Zernio MCP — Sales Manager'in ihtiyaci olabilir (reklam analitik,
    # post performansi). Lifespan ile connect edilmis aktif server'lari al.
    from src.infra.zernio.mcp_server import get_active_mcp_servers
    mcp_servers = get_active_mcp_servers()

    return Agent(
        name="sales_manager",
        handoff_description=(
            "Satis Muduru: NocoDB CRM uzerinden lead/outreach/auto-reply "
            "durumunu raporlar, aksiyon onerir. Alt birim (Avci, DM "
            "Yanitlayici) durumlarini izler; yan birim (Reklam Uzmani) "
            "ile koordine olur. Yazma yapmaz — su an okuma + danismanlik."
        ),
        instructions=BRAND_AWARE_PREFIX + SALES_MANAGER_INSTRUCTIONS,
        tools=tools,
        mcp_servers=mcp_servers,
        tool_use_behavior="run_llm_again",
        output_type=str,
        # gpt-4o-mini: ucuz, hizli, raporlama icin yeterli. Zernio MCP
        # ~80 tool yuku gpt-4o'nun TPM limitini asiyordu (Sales Analyst
        # zamani tespit edildi). mini'nin TPM limiti yuksek.
        model=model or "gpt-4o-mini",
    )


__all__ = ["create_sales_manager_agent"]
