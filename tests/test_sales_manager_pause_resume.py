"""Tests for outreach_pause / outreach_resume tools (Sales Manager write authority)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    client.update_record.return_value = {"Id": 1, "outreach_paused": True}
    from src.tools.sales import reporting_tools
    monkeypatch.setattr(reporting_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
    return client


class TestPause:
    @pytest.mark.asyncio
    async def test_pause_success(self, mock_nocodb):
        from src.tools.sales.reporting_tools import _outreach_pause_impl

        result = await _outreach_pause_impl(reason="Reply rate dustu")
        assert result["success"] is True
        assert result["paused"] is True
        assert "Reply rate" in result["summary_tr"]
        mock_nocodb.update_record.assert_called_once()
        args = mock_nocodb.update_record.call_args
        assert args.args[0] == "settings_tbl"
        assert args.args[1] == 1
        fields = args.args[2]
        assert fields["outreach_paused"] is True
        assert fields["pause_reason"] == "Reply rate dustu"
        assert "paused_at" in fields

    @pytest.mark.asyncio
    async def test_pause_missing_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        from src.tools.sales.reporting_tools import _outreach_pause_impl

        result = await _outreach_pause_impl(reason="x")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_pause_nocodb_exception_classified(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        client = MagicMock()
        client.update_record.side_effect = RuntimeError("boom")
        from src.tools.sales import reporting_tools
        monkeypatch.setattr(reporting_tools, "get_nocodb_client", lambda: client)

        result = await reporting_tools._outreach_pause_impl(reason="x")
        assert result["success"] is False


class TestResume:
    @pytest.mark.asyncio
    async def test_resume_success(self, mock_nocodb):
        from src.tools.sales.reporting_tools import _outreach_resume_impl

        result = await _outreach_resume_impl()
        assert result["success"] is True
        assert result["paused"] is False
        mock_nocodb.update_record.assert_called_once()
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["outreach_paused"] is False
        assert fields["pause_reason"] == ""
        assert "resumed_at" in fields

    @pytest.mark.asyncio
    async def test_resume_missing_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        from src.tools.sales.reporting_tools import _outreach_resume_impl

        result = await _outreach_resume_impl()
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


class TestRegistration:
    def test_get_management_tools_exposes_both(self):
        from src.tools.sales.reporting_tools import get_management_tools

        tools = get_management_tools()
        names = {t.name for t in tools}
        assert names == {"outreach_pause", "outreach_resume"}

    def test_sales_manager_has_management_tools(self):
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent

        agent = create_sales_manager_agent()
        names = {t.name for t in agent.tools}
        assert "outreach_pause" in names
        assert "outreach_resume" in names
