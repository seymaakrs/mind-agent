"""Sales Analyst Agent — NocoDB Leadler + Etkilesimler tablolarindan READ-ONLY
rapor uretir. Hicbir yazma yapmaz."""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.tools.sales.reporting_tools import get_reporting_tools
from src.agents.instructions.sales import SALES_ANALYST_INSTRUCTIONS


def create_sales_analyst_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """Sales Analyst agent factory.

    Tool seti: count_leads, list_leads, lead_funnel, channel_breakdown,
    stale_leads, lead_timeline, daily_digest. Hepsi read-only.
    """
    tools = list(get_reporting_tools())

    # Zernio MCP — analytics + reports (IG demographics, posting frequency,
    # best time, content decay, post-timeline, ads analytics). Lifespan
    # ile connect edilmis aktif server'lari al.
    from src.infra.zernio.mcp_server import get_active_mcp_servers
    mcp_servers = get_active_mcp_servers()

    return Agent(
        name="sales_analyst",
        handoff_description=(
            "Sales Analyst: NocoDB CRM (Leadler + Etkilesimler) uzerinden "
            "okuma yaparak rapor, sayim, liste, dagilim, trend cevabi uretir. "
            "Yazma yapmaz. Zernio MCP araciligi ile reklam/post/analytics "
            "raporlari da donebilir."
        ),
        instructions=SALES_ANALYST_INSTRUCTIONS,
        tools=tools,
        mcp_servers=mcp_servers,
        tool_use_behavior="run_llm_again",
        output_type=str,
        # gpt-4o-mini: Zernio MCP ~80 tool semasi prompt'u sisirip gpt-4o'nun
        # 30k TPM limitini asiyordu (429 -> ~30s -> gorev cokuyordu). mini'nin
        # TPM limiti cok yuksek; rapor anlatimi icin yeterli. Override edilebilir.
        model=model or "gpt-4o-mini",
    )


__all__ = ["create_sales_analyst_agent"]
