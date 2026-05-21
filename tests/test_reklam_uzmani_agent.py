"""Tests for Reklam Uzmani (eski: Meta) agent and NocoDB tools wiring."""
from __future__ import annotations

import os

import pytest

# Tests need a fake OPENAI_API_KEY to import the agents module.
os.environ.setdefault("OPENAI_API_KEY", "test")


class TestReklamUzmaniAgentWiring:
    def test_agent_has_six_nocodb_tools(self):
        from src.agents.sales.reklam_uzmani_agent import create_reklam_uzmani_agent

        agent = create_reklam_uzmani_agent()
        tool_names = [t.name for t in agent.tools]
        assert agent.name == "reklam_uzmani"
        assert set(tool_names) == {
            "upsert_lead",
            "update_lead",
            "get_lead",
            "query_leads",
            "log_lead_message",
            "notify_seyma",
        }

    def test_registry_exposes_reklam_uzmani(self):
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        # Yeni canonical isim
        assert "reklam_uzmani" in registry
        agent = registry["reklam_uzmani"]()
        assert agent.name == "reklam_uzmani"

    def test_registry_keeps_meta_alias_for_back_compat(self):
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        # Geriye donuk uyum
        assert "meta" in registry
        agent = registry["meta"]()
        assert agent.name == "reklam_uzmani"  # alias ayni agent'a baglanir

    def test_orchestrator_includes_reklam_uzmani_tool(self):
        from src.agents.orchestrator_agent import create_orchestrator_agent

        orchestrator = create_orchestrator_agent()
        tool_names = [t.name for t in orchestrator.tools]
        assert "reklam_uzmani_tool" in tool_names

    def test_orchestrator_instructions_mention_reklam_uzmani(self):
        from src.agents.instructions import build_orchestrator_instructions

        text = build_orchestrator_instructions("2026-04-28")
        assert "reklam_uzmani_tool" in text
        assert "META LEAD" in text or "meta lead" in text.lower()


class TestNocoDBToolsConfigGuard:
    def test_create_lead_returns_error_when_table_id_missing(self, monkeypatch):
        from src.app import config

        # Force missing leads table id
        config.get_settings.cache_clear()
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)

        from src.tools.sales.nocodb_tools import (
            _resolve_leads_table,
            _missing_table_error,
        )
        assert _resolve_leads_table() is None
        err = _missing_table_error("leads")
        assert err["success"] is False
        assert err["error_code"] == "INVALID_INPUT"
        assert err["service"] == "nocodb"
