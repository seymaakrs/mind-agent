"""Auto-reply pause/resume (Sales Director write) + runner flag check."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    client.update_record.return_value = {"Id": 1, "auto_reply_paused": True}
    from src.tools.sales import management_tools
    monkeypatch.setattr(management_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
    return client


class TestAutoReplyPause:
    @pytest.mark.asyncio
    async def test_pause_success(self, mock_nocodb):
        from src.tools.sales.management_tools import _auto_reply_pause_impl
        result = await _auto_reply_pause_impl(reason="Ton kontrolu")
        assert result["success"] is True
        assert result["paused"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["auto_reply_paused"] is True
        assert fields["auto_reply_pause_reason"] == "Ton kontrolu"
        assert "auto_reply_paused_at" in fields

    @pytest.mark.asyncio
    async def test_resume_success(self, mock_nocodb):
        from src.tools.sales.management_tools import _auto_reply_resume_impl
        result = await _auto_reply_resume_impl()
        assert result["success"] is True
        assert result["paused"] is False
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["auto_reply_paused"] is False
        assert fields["auto_reply_pause_reason"] == ""
        assert "auto_reply_resumed_at" in fields

    @pytest.mark.asyncio
    async def test_pause_missing_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        from src.tools.sales.management_tools import _auto_reply_pause_impl
        result = await _auto_reply_pause_impl(reason="x")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


class TestRunnerFlagCheck:
    def test_is_paused_true_when_flag_set(self, monkeypatch):
        client = MagicMock()
        client.list_records.return_value = {"list": [{"auto_reply_paused": True}]}
        from src.agents.auto_reply import runner
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: client)
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        assert runner._is_paused() is True

    def test_is_paused_false_when_flag_unset(self, monkeypatch):
        client = MagicMock()
        client.list_records.return_value = {"list": [{"auto_reply_paused": False}]}
        from src.agents.auto_reply import runner
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: client)
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        assert runner._is_paused() is False

    def test_is_paused_no_env_returns_false(self, monkeypatch):
        from src.agents.auto_reply import runner
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        assert runner._is_paused() is False

    def test_is_paused_nocodb_error_returns_false(self, monkeypatch):
        client = MagicMock()
        client.list_records.side_effect = RuntimeError("boom")
        from src.agents.auto_reply import runner
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: client)
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        # Defensive: assume active on error
        assert runner._is_paused() is False
