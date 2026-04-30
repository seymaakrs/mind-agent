"""Smoke tests for all sales agents (clay, ig_dm, linkedin, meta_lead).

Verifies each agent:
- Is constructable without external dependencies (Firebase patched)
- Has the right tool set wired
- Has Turkish handoff description
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_firebase():
    """Patch get_model_settings on every sales agent module path."""
    paths = [
        "src.agents.sales.clay_agent.get_model_settings",
        "src.agents.sales.ig_dm_agent.get_model_settings",
        "src.agents.sales.linkedin_agent.get_model_settings",
        "src.agents.sales.meta_lead_agent.get_model_settings",
        "src.agents.sales.sales_query_agent.get_model_settings",
    ]
    patches = [patch(p) for p in paths]
    mocks = [p.start() for p in patches]
    for m in mocks:
        m.return_value = MagicMock(orchestrator_model="gpt-4o")
    yield
    for p in patches:
        p.stop()


class TestAgentConstruction:
    def test_clay_agent_builds(self) -> None:
        from src.agents.sales import create_clay_agent

        agent = create_clay_agent()
        assert agent.name == "clay"

    def test_ig_dm_agent_builds(self) -> None:
        from src.agents.sales import create_ig_dm_agent

        agent = create_ig_dm_agent()
        assert agent.name == "ig_dm"

    def test_linkedin_agent_builds(self) -> None:
        from src.agents.sales import create_linkedin_agent

        agent = create_linkedin_agent()
        assert agent.name == "linkedin"

    def test_meta_lead_agent_builds(self) -> None:
        from src.agents.sales import create_meta_lead_agent

        agent = create_meta_lead_agent()
        assert agent.name == "meta_lead"

    def test_sales_query_agent_builds(self) -> None:
        from src.agents.sales import create_sales_query_agent

        agent = create_sales_query_agent()
        assert agent.name == "sales_query"


class TestAgentToolsets:
    """Each agent should have only the tools relevant to its role."""

    def test_clay_includes_discovery_and_scoring(self) -> None:
        from src.agents.sales import create_clay_agent

        names = {t.name for t in create_clay_agent().tools}
        assert {
            "discover_local_businesses",
            "score_business_presence",
            "generate_outreach_message",
            "create_lead",
            "log_lead_message",
            "notify_seyma",
            "query_leads",
        }.issubset(names)

    def test_ig_dm_includes_zernio_dm(self) -> None:
        from src.agents.sales import create_ig_dm_agent

        names = {t.name for t in create_ig_dm_agent().tools}
        assert "send_zernio_dm" in names
        assert "list_zernio_dm_threads" in names
        assert "create_lead" in names
        assert "notify_seyma" in names
        # Should NOT have ad campaign tools
        assert "pause_zernio_campaign" not in names

    def test_linkedin_includes_outreach_and_dm(self) -> None:
        from src.agents.sales import create_linkedin_agent

        names = {t.name for t in create_linkedin_agent().tools}
        assert "send_zernio_dm" in names
        assert "generate_outreach_message" in names
        assert "create_lead" in names
        # Should NOT have ad campaign tools
        assert "pause_zernio_campaign" not in names

    def test_meta_lead_includes_ads_management(self) -> None:
        from src.agents.sales import create_meta_lead_agent

        names = {t.name for t in create_meta_lead_agent().tools}
        assert "pause_zernio_campaign" in names
        assert "get_zernio_campaign_metrics" in names
        assert "get_zernio_account_analytics" in names
        # Lead processing tools also present (will activate when App Live)
        assert "create_lead" in names
        assert "notify_seyma" in names
        # Should NOT have DM tools (Meta lead form != DM channel)
        assert "send_zernio_dm" not in names


class TestAgentDescriptionsAreTurkish:
    def test_each_agent_has_turkish_description(self) -> None:
        from src.agents.sales import (
            create_clay_agent,
            create_ig_dm_agent,
            create_linkedin_agent,
            create_meta_lead_agent,
            create_sales_query_agent,
        )

        agents = [
            create_clay_agent(),
            create_ig_dm_agent(),
            create_linkedin_agent(),
            create_meta_lead_agent(),
            create_sales_query_agent(),
        ]
        for a in agents:
            desc = a.handoff_description
            # very loose Turkish-ness check: should contain at least one Turkish-only character
            # OR a Turkish keyword we use across descriptions.
            tr_markers = ("ı", "ğ", "ü", "ş", "ö", "ç", "İ", "Ğ", "Ş")
            assert any(c in desc for c in tr_markers), (
                f"{a.name} description not Turkish: {desc[:80]}..."
            )
