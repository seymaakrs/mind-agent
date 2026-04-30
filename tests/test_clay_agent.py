"""Clay agent wiring tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_firebase_dependent_calls():
    with patch("src.agents.sales.clay_agent.get_model_settings") as mock_ms:
        mock_ms.return_value = MagicMock(orchestrator_model="gpt-4o")
        yield


def _create_agent():
    from src.agents.sales import create_clay_agent
    return create_clay_agent()


class TestClayAgent:
    def test_agent_created(self) -> None:
        agent = _create_agent()
        assert agent.name == "clay"

    def test_agent_has_required_tools(self) -> None:
        agent = _create_agent()
        names = {t.name for t in agent.tools}
        assert "discover_local_businesses" in names
        assert "score_business_presence" in names
        assert "generate_outreach_message" in names
        assert "create_lead" in names
        assert "log_lead_message" in names
        assert "notify_seyma" in names

    def test_agent_can_query_to_avoid_duplicates(self) -> None:
        # Clay needs read access to check existing leads before creating duplicates.
        agent = _create_agent()
        names = {t.name for t in agent.tools}
        assert "query_leads" in names

    def test_agent_handoff_description_is_turkish(self) -> None:
        agent = _create_agent()
        desc = agent.handoff_description.lower()
        # mentions our target (Bodrum/Muğla) and key concepts
        assert "bodrum" in desc or "muğla" in desc
        assert "lead" in desc or "i̇şletme" in desc or "işletme" in desc
