"""Orchestrator <-> sales wiring smoke tests.

Verifies:
- SALES_AGENTS_ENABLED=False -> orchestrator has the same tool set as before
- SALES_AGENTS_ENABLED=True  -> orchestrator gains exactly 5 sales wrappers
- The 5 wrappers have distinct names matching the registered tool ids
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _patches(sales_enabled: bool):
    """Common patch dict — Firebase-touching helpers stubbed."""
    settings = MagicMock(sales_agents_enabled=sales_enabled, openai_model=None)
    ms = MagicMock(
        orchestrator_model="gpt-4o",
        image_agent_model="gpt-4o",
        video_agent_model="gpt-4o",
        marketing_agent_model="gpt-4o",
        analysis_agent_model="gpt-4o",
    )
    return settings, ms


def _build_orchestrator(sales_enabled: bool):
    settings, ms = _patches(sales_enabled)
    paths_settings = [
        "src.agents.orchestrator_agent.get_settings",
        "src.agents.marketing_agent.get_settings",
        "src.agents.image_agent.get_settings",
        "src.agents.video_agent.get_settings",
    ]
    paths_ms = [
        "src.agents.orchestrator_agent.get_model_settings",
        "src.agents.marketing_agent.get_model_settings",
        "src.agents.image_agent.get_model_settings",
        "src.agents.video_agent.get_model_settings",
        "src.agents.analysis_agent.get_model_settings",
    ]
    patchers = []
    for p in paths_settings:
        m = patch(p)
        patchers.append((m, m.start()))
        patchers[-1][1].return_value = settings
    for p in paths_ms:
        m = patch(p)
        patchers.append((m, m.start()))
        patchers[-1][1].return_value = ms
    try:
        from src.agents.orchestrator_agent import create_orchestrator_agent

        return create_orchestrator_agent(), len(patchers)
    finally:
        for p, _ in patchers:
            p.stop()


SALES_TOOL_NAMES = {
    "sales_query_agent_tool",
    "clay_agent_tool",
    "ig_dm_agent_tool",
    "linkedin_agent_tool",
    "meta_lead_agent_tool",
}


class TestOrchestratorSalesWiring:
    def test_disabled_does_not_include_sales_tools(self) -> None:
        agent, _ = _build_orchestrator(sales_enabled=False)
        names = {t.name for t in agent.tools}
        assert SALES_TOOL_NAMES.isdisjoint(names), (
            f"Sales tools leaked when disabled: {SALES_TOOL_NAMES & names}"
        )

    def test_enabled_includes_all_five_sales_tools(self) -> None:
        agent, _ = _build_orchestrator(sales_enabled=True)
        names = {t.name for t in agent.tools}
        assert SALES_TOOL_NAMES.issubset(names), (
            f"Missing sales tools: {SALES_TOOL_NAMES - names}"
        )

    def test_toggle_diff_is_exactly_five(self) -> None:
        agent_off, _ = _build_orchestrator(sales_enabled=False)
        agent_on, _ = _build_orchestrator(sales_enabled=True)
        assert len(agent_on.tools) - len(agent_off.tools) == 5
