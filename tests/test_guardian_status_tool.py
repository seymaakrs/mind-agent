"""Tests for guardian_tools.get_guardian_status — Sef reads Bekci state."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)


class TestGetGuardianStatus:
    @pytest.mark.asyncio
    async def test_returns_error_when_settings_table_not_configured(self):
        from src.tools.guardian_tools import _get_guardian_status_impl

        result = await _get_guardian_status_impl()
        assert result["success"] is False
        assert result["configured"] is False
        assert "NOCODB_SETTINGS_TABLE_ID" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_insufficient_when_table_empty(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.tools import guardian_tools

        mock_client = MagicMock()
        mock_client.list_records.return_value = {"list": []}
        monkeypatch.setattr(
            guardian_tools, "get_nocodb_client", lambda: mock_client
        )

        result = await guardian_tools._get_guardian_status_impl()
        assert result["success"] is True
        assert result["level"] == "INSUFFICIENT"
        assert "Bekci henuz tick atmadi" in result["summary"]

    @pytest.mark.asyncio
    async def test_returns_green_state(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.tools import guardian_tools

        mock_client = MagicMock()
        mock_client.list_records.return_value = {
            "list": [{
                "last_decision_level": "GREEN",
                "last_recommended_action": "NONE",
                "last_decision_reason": "all green",
                "last_health_check": "2026-05-20T15:30:00+00:00",
                "outreach_paused": False,
                "last_metrics_json": json.dumps({
                    "outreach_sent": 120,
                    "inbound_received": 9,
                    "reply_rate_pct": 7.5,
                    "engagement_rate_pct": 66.6,
                }),
            }]
        }
        monkeypatch.setattr(
            guardian_tools, "get_nocodb_client", lambda: mock_client
        )

        result = await guardian_tools._get_guardian_status_impl()
        assert result["success"] is True
        assert result["level"] == "GREEN"
        assert result["outreach_paused"] is False
        assert "SAĞLIKLI" in result["summary"]
        assert "120 outreach" in result["summary"]

    @pytest.mark.asyncio
    async def test_returns_red_with_pause_info(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.tools import guardian_tools

        mock_client = MagicMock()
        mock_client.list_records.return_value = {
            "list": [{
                "last_decision_level": "RED",
                "last_recommended_action": "PAUSE",
                "last_decision_reason": "reply_rate 1.2% < red 3%",
                "outreach_paused": True,
                "pause_reason": "reply_rate 1.2% < red 3%",
                "paused_at": "2026-05-20T15:00:00+00:00",
                "last_health_check": "2026-05-20T15:30:00+00:00",
            }]
        }
        monkeypatch.setattr(
            guardian_tools, "get_nocodb_client", lambda: mock_client
        )

        result = await guardian_tools._get_guardian_status_impl()
        assert result["success"] is True
        assert result["level"] == "RED"
        assert result["outreach_paused"] is True
        assert "KRİTİK" in result["summary"]
        assert "DURDURULMUS" in result["summary"]

    @pytest.mark.asyncio
    async def test_nocodb_error_returns_clean_failure(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.tools import guardian_tools

        mock_client = MagicMock()
        mock_client.list_records.side_effect = RuntimeError("connection refused")
        monkeypatch.setattr(
            guardian_tools, "get_nocodb_client", lambda: mock_client
        )

        result = await guardian_tools._get_guardian_status_impl()
        assert result["success"] is False
        assert "RuntimeError" in result["error"]


class TestOrchestratorWiring:
    def test_orchestrator_has_get_guardian_status(self):
        """Orchestrator agent factory tool listesinde get_guardian_status olmali."""
        from src.agents.orchestrator_agent import create_orchestrator_agent

        agent = create_orchestrator_agent()
        tool_names = {t.name for t in agent.tools}
        assert "get_guardian_status" in tool_names, (
            f"Orchestrator missing get_guardian_status. Got: {tool_names}"
        )
