"""Sales Director (Satis Direktoru) — Faz 1 yukseltmesi.

Eski adlari: Sales Analyst (read-only rapor) -> Sales Manager (read + outreach
pause/resume) -> **Sales Director** (yazma + hafiza + brand + pipeline + KPI).

Faz 2 (alt mudurler — Avci Muduru, DM Muduru, Reklam Muduru) sonraki PR'da.
Su an Direktor TEK figur, ~37 tool eline veriliyor.

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
from src.tools.sales.peer_bridge import get_peer_bridge_tools
from src.tools.sales.reporting_tools import get_reporting_tools
from src.tools.sales.manager_actions import get_manager_action_tools
from src.tools.sales.memory_tools import get_sales_memory_tools
from src.tools.sales.goals_tools import get_goal_tools
from src.tools.sales.triage_tools import get_triage_tools
from src.tools.brand import fetch_brand_identity
from src.agents.instructions.sales import SALES_MANAGER_INSTRUCTIONS  # noqa: F401
from src.agents.instructions.brand_aware import BRAND_AWARE_PREFIX


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

    Tool seti: 10 read + 6 PR write (manager_actions, SoT) + 6 main additive
    write/analytics (management_tools, non-overlap) + 3 memory + 3 goals
    + 2 triage + 5 knowledge + 1 peer-bridge + 1 brand = 37 tool.
    """
    # main's management_tools — non-overlapping subset
    # (outreach_pause/resume already in manager_actions; skip those + the dup
    #  assign_lead which is PR's lead_reassign by another name)
    from src.tools.sales.management_tools import (
        add_lead_note,
        auto_reply_pause,
        auto_reply_resume,
        pipeline_forecast,
        update_lead_stage,
        weekly_kpi,
    )

    tools = (
        list(get_reporting_tools())          # 10 okuma
        + list(get_manager_action_tools())   # 6 yazma (PR TODO A — SoT)
        + [                                  # 6 yazma/analytics (main, additive)
            auto_reply_pause,
            auto_reply_resume,
            update_lead_stage,
            add_lead_note,
            pipeline_forecast,
            weekly_kpi,
        ]
        + list(get_sales_memory_tools())     # 3 memory (A2 — structured)
        + list(get_goal_tools())             # 3 aylık hedef + KPI (B1)
        + list(get_triage_tools())           # 2 sıcak lead triage (C1)
        + list(get_knowledge_tools())        # 5 knowledge (main, additive)
        + list(get_peer_bridge_tools())      # 1 peer bridge (main, additive)
        + [fetch_brand_identity]             # 1 brand
    )  # toplam 37 tool

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
        instructions=BRAND_AWARE_PREFIX + instructions,
        tools=tools,
        mcp_servers=mcp_servers,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or "gpt-4o-mini",
    )


__all__ = ["create_sales_manager_agent"]
