"""Tests for Sales Manager agent wiring (skeleton).

Sales Manager (eski Sales Analyst) okuma + danismanlik agent'i.
Mevcut read tool setini koruyor, persona yonetici. Yazma tool'lari TODO.

LLM cagrilmaz (offline wiring tests).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


class TestSalesManagerFactory:
    def test_agent_name_and_handoff(self):
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        assert agent.name == "sales_manager"
        assert agent.handoff_description
        assert "satis muduru" in agent.handoff_description.lower()

    def test_agent_has_all_read_tools(self):
        """Sales Manager mevcut 10 read tool'u korumalı."""
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        tool_names = {t.name for t in agent.tools}
        required = {
            "count_leads",
            "list_leads",
            "lead_funnel",
            "channel_breakdown",
            "stale_leads",
            "lead_timeline",
            "daily_digest",
            "outreach_status",
            "auto_reply_status",
            "outreach_health",
        }
        missing = required - tool_names
        assert not missing, f"Missing read tools: {missing}"

    def test_agent_has_all_write_tools(self):
        """TODO A tamam: 6 yazma yetkisi Muduere bagli."""
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        tool_names = {t.name for t in agent.tools}
        required_writes = {
            "outreach_pause",
            "outreach_resume",
            "lead_reassign",
            "lead_priority_set",
            "auto_reply_template_update",
            "outreach_daily_limit_set",
        }
        missing = required_writes - tool_names
        assert not missing, f"Eksik yazma tool'lari: {missing}"


class TestSalesManagerInstructions:
    def test_instructions_constant_exported(self):
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        assert isinstance(SALES_MANAGER_INSTRUCTIONS, str)
        assert len(SALES_MANAGER_INSTRUCTIONS) > 500

    def test_instructions_describe_manager_role(self):
        """Persona analyst degil, manager olmali."""
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        text = SALES_MANAGER_INSTRUCTIONS.lower()
        assert "satis muduru" in text or "sales manager" in text
        # Alt birimler ve yan birim referansi
        assert "avci" in text
        assert "dm yanitlayici" in text or "auto-reply" in text
        assert "reklam uzmani" in text or "meta" in text
        # NocoDB tek SoT
        assert "nocodb" in text

    def test_instructions_describe_write_authority(self):
        """TODO A sonrasi: persona yazma yetkilerini ve gerekce kuralini anlatmali."""
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        text = SALES_MANAGER_INSTRUCTIONS.lower()
        assert "yazma" in text
        assert "outreach_pause" in text
        assert "lead_reassign" in text
        assert "gerekce" in text or "sebep" in text  # audit log icin sebep zorunlu


class TestRegistry:
    def test_registry_exposes_sales_manager(self):
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        assert "sales_manager" in registry
        agent = registry["sales_manager"]()
        assert agent.name == "sales_manager"

    def test_registry_keeps_sales_analyst_for_backcompat(self):
        """Eski sales_analyst alias kaldigi surece backwards-compat."""
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        # Deprecated ama hala calismali
        assert "sales_analyst" in registry


class TestOrchestratorWiring:
    def test_orchestrator_has_sales_manager_tool(self):
        from src.agents.orchestrator_agent import create_orchestrator_agent

        agent = create_orchestrator_agent()
        tool_names = {t.name for t in agent.tools}
        assert "sales_manager_tool" in tool_names, (
            f"Orchestrator missing sales_manager_tool. Got: {tool_names}"
        )

    def test_orchestrator_no_longer_has_sales_analyst_tool(self):
        """Sef artik analyst yerine manager kullanmali."""
        from src.agents.orchestrator_agent import create_orchestrator_agent

        agent = create_orchestrator_agent()
        tool_names = {t.name for t in agent.tools}
        # sales_analyst_tool artik wiring'de yok
        assert "sales_analyst_tool" not in tool_names

    def test_orchestrator_does_not_have_direct_post_tools(self):
        """Defense-in-depth: Şef post atmaz, marketing/video agent'a delege eder.

        post_on_instagram + post_carousel_on_instagram + tiktok/youtube/linkedin
        post tool'lari Şef'in elinde OLMAMALI (instructions yasak diyor zaten,
        ama dosya erisimi de olmasin).
        """
        from src.tools.orchestrator import get_orchestrator_tools

        tool_names = {t.name for t in get_orchestrator_tools()}
        forbidden = {
            "post_on_instagram",
            "post_carousel_on_instagram",
            "post_on_tiktok",
            "post_carousel_on_tiktok",
            "post_on_youtube",
            "post_on_linkedin",
            "post_carousel_on_linkedin",
        }
        leaked = forbidden & tool_names
        assert not leaked, f"Şef'in elinde olmamasi gereken post tool'lari: {leaked}"


class TestSalesManagerBrandAndPeer:
    """QA paketi: #4 (peer wiring) + #7 (brand awareness)."""

    def test_agent_has_fetch_brand_identity(self):
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            "Sales Manager markaya gore yorum yapabilmek icin "
            "fetch_brand_identity tool'unu kullanmali."
        )

    def test_instructions_include_brand_aware_prefix(self):
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        # BRAND_AWARE_PREFIX'in karakteristik basligi
        assert "ZORUNLU ILK ADIM" in agent.instructions
        assert "fetch_brand_identity" in agent.instructions

    def test_instructions_describe_peer_handoff_with_meta(self):
        """Sales Manager Reklam Uzmani'na Şef üzerinden handoff onerisi vermeli."""
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        text = SALES_MANAGER_INSTRUCTIONS.lower()
        assert "peer" in text or "es duzey" in text or "eş düzey" in text or "yatay" in text
        assert "yonlendir" in text or "handoff" in text
