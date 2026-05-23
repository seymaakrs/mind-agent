"""Pazarlama Müdürü (Marketing Director) wiring testleri.

2026-05-22: Marketing Agent "Pazarlama Müdürü" kimliğine yükseltildi.
Knowledge tools eklendi (ürün/kitle/ses hakimiyeti) ve instructions'a
müdür rolü + disiplin + içerik üretim akışı eklendi.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


class TestMarketingDirectorTools:
    def test_marketing_has_knowledge_tools(self):
        """Pazarlama Müdürü ürün/kitle/ses bilgisini knowledge_tools ile okur."""
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        tool_names = {t.name for t in agent.tools}
        required_knowledge = {
            "get_product_catalog",
            "get_target_audience",
            "get_brand_voice",
            "get_unique_value_proposition",
            "get_sales_playbook",
        }
        missing = required_knowledge - tool_names
        assert not missing, f"Marketing missing knowledge tools: {missing}"

    def test_marketing_has_brand_identity_fetch(self):
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names

    def test_marketing_has_posting_tools(self):
        """Post atma Marketing'in iş — Sales'tan farklı olarak bu yetkili."""
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        tool_names = {t.name for t in agent.tools}
        assert "post_on_instagram" in tool_names

    def test_marketing_name_stable(self):
        """Agent.name 'marketing' kalmali — orchestrator routing kirilmasin."""
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        assert agent.name == "marketing"


class TestMarketingDirectorInstructions:
    def test_director_identity_in_instructions(self):
        """Yeni 'Pazarlama Müdürü' kimliği instructions'a girdi mi?"""
        from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS

        assert "Pazarlama Müdürü" in MARKETING_AGENT_INSTRUCTIONS or \
               "Marketing Director" in MARKETING_AGENT_INSTRUCTIONS

    def test_discipline_clause_present(self):
        from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS

        assert "DISIPLIN" in MARKETING_AGENT_INSTRUCTIONS or \
               "DİSİPLİN" in MARKETING_AGENT_INSTRUCTIONS

    def test_content_pipeline_referenced(self):
        """get_sales_playbook akışın ilk adımı olmalı."""
        from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS

        assert "get_sales_playbook" in MARKETING_AGENT_INSTRUCTIONS
