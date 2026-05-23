"""Tests for Auto-reply daily cap (cost ceiling)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.auto_reply import runner  # noqa: E402
from src.agents.auto_reply.policy import AutoReplyConfig  # noqa: E402
from src.agents.auto_reply.responder import AutoReplyDecision  # noqa: E402


def _decision(intent="olumlu", reply="cevap", conf=0.9):
    return AutoReplyDecision(
        intent=intent, reply_text=reply, confidence=conf, objection_type=None
    )


@pytest.fixture
def mock_clients(monkeypatch):
    nocodb = MagicMock()
    nocodb.find_by_field.return_value = {"Id": 42, "telefon": "+905551112233"}
    zernio = MagicMock()
    zernio.find_conversation_by_phone = AsyncMock(return_value={"id": "conv-1"})
    zernio.send_message = AsyncMock(return_value={"messageId": "wamid.OUT"})
    monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
    monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio)

    async def fake_decide(message, **kwargs):
        return _decision()
    monkeypatch.setattr(runner, "decide_reply", fake_decide)
    return nocodb, zernio


class TestDailyCap:
    def test_config_default_is_100(self):
        c = AutoReplyConfig()
        assert c.daily_cap == 100

    def test_config_env_override(self, monkeypatch):
        monkeypatch.setenv("AUTO_REPLY_DAILY_CAP", "25")
        c = AutoReplyConfig.from_env()
        assert c.daily_cap == 25

    @pytest.mark.asyncio
    async def test_cap_zero_means_disabled(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        # If cap is queried, return huge — but cap=0 should short-circuit
        monkeypatch.setattr(
            runner, "_count_auto_replies_sent_today", lambda *a, **kw: 999_999
        )
        config = AutoReplyConfig(daily_cap=0)
        result = await runner.handle_one(
            inbound_row={"Id": 1, "mesaj_icerigi": "evet", "lead_adi": "Otel"},
            config=config,
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is True

    @pytest.mark.asyncio
    async def test_cap_not_reached_sends(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        monkeypatch.setattr(
            runner, "_count_auto_replies_sent_today", lambda *a, **kw: 5
        )
        config = AutoReplyConfig(daily_cap=10)
        result = await runner.handle_one(
            inbound_row={"Id": 2, "mesaj_icerigi": "evet", "lead_adi": "Otel"},
            config=config,
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is True

    @pytest.mark.asyncio
    async def test_cap_reached_skips_and_marks_processed(
        self, mock_clients, monkeypatch
    ):
        nocodb, zernio = mock_clients
        monkeypatch.setattr(
            runner, "_count_auto_replies_sent_today", lambda *a, **kw: 10
        )
        config = AutoReplyConfig(daily_cap=10)
        result = await runner.handle_one(
            inbound_row={"Id": 3, "mesaj_icerigi": "evet", "lead_adi": "Otel"},
            config=config,
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is False
        assert result.get("skipped") == "daily_cap"
        zernio.send_message.assert_not_called()
        # marked processed so we don't retry forever
        nocodb.update_record.assert_called_with(
            "msgs_tbl", 3, {"auto_reply_processed": True}
        )
