"""Sales Director (Satis Direktoru) — Faz 1 yukseltmesi.

Eski adlari: Sales Analyst (read-only rapor) -> Sales Manager (read + outreach
pause/resume) -> **Sales Director** (yazma + hafiza + brand + pipeline + KPI).

Faz 2 (alt mudurler — Avci Muduru, DM Muduru, Reklam Muduru) sonraki PR'da.
Su an Direktor TEK figur, ~22 tool eline veriliyor.

NOT: Agent.name STRING'i 'sales_manager' olarak KALIYOR — orchestrator routing
'sales_manager_tool' uzerinden gidiyor. handoff_description 'Satis Direktoru'
olarak guncellendi.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agents import Agent

from src.agents.instructions.sales import SALES_DIRECTOR_INSTRUCTIONS
from src.tools.sales.knowledge_tools import get_knowledge_tools
from src.tools.sales.management_tools import get_management_tools
from src.tools.sales.peer_bridge import get_peer_bridge_tools
from src.tools.sales.reporting_tools import get_reporting_tools


log = logging.getLogger(__name__)


def _build_brand_aware_instructions(base: str) -> str:
    """Optionally prepend brand identity context to instructions.

    Pattern mirror: src/agents/auto_reply/runner.py brand load. Env-controlled:
    SALES_DIRECTOR_BUSINESS_ID set ise yuklemeyi dener; basarisizsa warn + skip.
    """
    business_id = os.environ.get("SALES_DIRECTOR_BUSINESS_ID")
    if not business_id:
        return base
    try:
        from src.tools.brand import load_brand_identity
        bi = load_brand_identity(business_id)
        if bi is None:
            log.info(
                "sales_director: no brand_identity for business=%s (skipping prefix)",
                business_id,
            )
            return base
        summary = bi.prompt_summary()
        if not summary:
            return base
        log.info(
            "sales_director: brand_identity loaded business=%s chars=%d",
            business_id, len(summary),
        )
        return f"## BRAND CONTEXT\n{summary}\n\n" + base
    except Exception as exc:
        log.warning("sales_director: brand identity load failed: %s", exc)
        return base


def create_sales_manager_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """Sales Director agent factory.

    Tool seti (yaklasik 28): 10 read (reporting_tools) + 11 yonetim
    (management_tools — outreach + auto_reply pause/resume, lead writes,
    sales memory get/update, pipeline_forecast, weekly_kpi) + 5 knowledge
    (knowledge_tools — product/audience/voice/UVP/playbook, BrandIdentity
    okuma, urun hakimiyeti icin 2026-05-22'de eklendi) + 1 peer-bridge
    (ask_reklam_uzmani — Reklam Uzmanı'na senkron sorgu, 2026-05-22).
    """
    tools = (
        list(get_reporting_tools())
        + list(get_management_tools())
        + list(get_knowledge_tools())
        + list(get_peer_bridge_tools())
    )

    from src.infra.zernio.mcp_server import get_active_mcp_servers
    mcp_servers = get_active_mcp_servers()

    instructions = _build_brand_aware_instructions(SALES_DIRECTOR_INSTRUCTIONS)

    return Agent(
        name="sales_manager",  # IMMUTABLE — orchestrator routing kirilmasin
        handoff_description=(
            "Satis Direktoru: NocoDB CRM uzerinden lead/outreach/auto-reply "
            "durumunu yonetir, lead atar, asama gunceller, pipeline tahmini "
            "yapar, haftalik KPI takip eder, kalici hafizaya yazi yazar. "
            "Faz 1 holding mimarisi — alt mudurler (Avci/DM/Reklam) sonraki "
            "fazda."
        ),
        instructions=instructions,
        tools=tools,
        mcp_servers=mcp_servers,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or "gpt-4o-mini",
    )


__all__ = ["create_sales_manager_agent"]
