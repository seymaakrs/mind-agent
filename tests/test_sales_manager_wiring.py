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
        # Faz 1: Sales Manager -> Sales Director rename
        assert "direktor" in agent.handoff_description.lower()

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

    def test_agent_has_limited_write_tools(self):
        """Yazma yetkisi SINIRLI: yalniz outreach_pause/outreach_resume."""
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        tool_names = {t.name for t in agent.tools}
        # Bunlar olmali
        assert "outreach_pause" in tool_names
        assert "outreach_resume" in tool_names
        # Bunlar HALA olmamali
        forbidden = {"lead_reassign", "auto_reply_template_update"}
        leaked = forbidden & tool_names
        assert not leaked, f"Olmamasi gereken yazma tool'lari: {leaked}"


class TestSalesManagerInstructions:
    def test_instructions_constant_exported(self):
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        assert isinstance(SALES_MANAGER_INSTRUCTIONS, str)
        assert len(SALES_MANAGER_INSTRUCTIONS) > 500

    def test_instructions_describe_manager_role(self):
        """Persona analyst degil, manager olmali."""
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        text = SALES_MANAGER_INSTRUCTIONS.lower()
        # Faz 1: rename to Sales Director
        assert "satis direktoru" in text or "sales director" in text
        # Alt birimler ve yan birim referansi
        assert "avci" in text
        assert "dm yanitlayici" in text or "auto-reply" in text
        assert "reklam uzmani" in text or "meta" in text
        # NocoDB tek SoT
        assert "nocodb" in text

    def test_instructions_mention_no_write_yet(self):
        """Persona yazma yetkisi olmadigini ve TODO'da oldugunu soylemeli."""
        from src.agents.instructions import SALES_MANAGER_INSTRUCTIONS

        text = SALES_MANAGER_INSTRUCTIONS.lower()
        assert "yazma" in text
        assert "todo" in text or "okuma" in text


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
