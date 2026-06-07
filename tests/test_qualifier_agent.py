"""Faz 5 — Qualifier Agent construction testleri."""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test")


def _tool_names(agent):
    names = []
    for t in agent.tools:
        names.append(getattr(t, "name", None) or getattr(t, "__name__", ""))
    return names


class TestQualifierAgent:
    def test_create_returns_agent(self):
        from src.agents.sales.qualifier_agent import create_qualifier_agent
        agent = create_qualifier_agent()
        assert agent.name == "qualifier"

    def test_has_required_tools(self):
        from src.agents.sales.qualifier_agent import create_qualifier_agent
        names = _tool_names(create_qualifier_agent())
        assert "mark_lead_qualified" in names
        assert "get_lead" in names
        assert "query_leads" in names
        assert "notify_seyma" in names

    def test_registered_in_registry(self):
        from src.agents.registry import get_agent_registry
        registry = get_agent_registry()
        assert "qualifier" in registry
        agent = registry["qualifier"]()
        assert agent.name == "qualifier"

    def test_instructions_mention_icp_and_gate(self):
        from src.agents.instructions.sales import QUALIFIER_INSTRUCTIONS
        text = QUALIFIER_INSTRUCTIONS.lower()
        assert "icp" in text
        assert "qualified" in text
        # mail kapısının üçlü kuralı instructions'ta anlatılmalı
        assert "source" in text
