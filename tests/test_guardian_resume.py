"""Guardian kapali dongu — GREEN'de otomatik resume (insan onayi yok)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.guardian.decisions import (  # noqa: E402
    ACTION_NONE,
    ACTION_PAUSE,
    ACTION_RESUME,
    DecisionLevel,
    decide,
)
from src.agents.guardian.metrics import GuardianMetrics  # noqa: E402
from src.agents.guardian.policy import GuardianConfig  # noqa: E402
from src.agents.guardian import runner  # noqa: E402


def _metrics(out=200, inb=10, auto=6, fail=0):
    return GuardianMetrics(24, out, inb, auto, fail)


class TestDecideResumeAction:
    def test_green_recommends_resume(self):
        d = decide(_metrics(out=200, inb=20, auto=12), GuardianConfig())
        assert d.level == DecisionLevel.GREEN
        assert d.resume_outreach is True
        assert d.pause_outreach is False
        assert d.recommended_action == ACTION_RESUME

    def test_red_recommends_pause_not_resume(self):
        d = decide(_metrics(out=200, inb=4, auto=3), GuardianConfig())
        assert d.level == DecisionLevel.RED
        assert d.pause_outreach is True
        assert d.resume_outreach is False
        assert d.recommended_action == ACTION_PAUSE

    def test_yellow_no_action(self):
        d = decide(_metrics(out=200, inb=8, auto=5), GuardianConfig())
        assert d.level == DecisionLevel.YELLOW
        assert d.resume_outreach is False
        assert d.pause_outreach is False
        assert d.recommended_action == ACTION_NONE

    def test_insufficient_no_action(self):
        d = decide(_metrics(out=10), GuardianConfig())
        assert d.level == DecisionLevel.INSUFFICIENT
        assert d.resume_outreach is False
        assert d.recommended_action == ACTION_NONE


class TestRunnerAutoResume:
    @pytest.mark.asyncio
    async def test_green_tick_clears_pause_flag(self, monkeypatch):
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        # 200 out, 20 inbound (10%), 15 auto (75%) -> GREEN
        nocodb.list_records.side_effect = [
            {"list": [{"Id": i} for i in range(200)]},
            {"list": [{"Id": i} for i in range(20)]},
            {"list": [{"Id": i} for i in range(15)]},
        ]
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(runner, "_send_alert_webhook", AsyncMock())

        result = await runner.tick(GuardianConfig())
        assert result["level"] == "GREEN"
        assert result["action"] == "RESUME"

        fields = nocodb.update_record.call_args.args[2]
        assert fields["outreach_paused"] is False
        assert fields["pause_reason"] == ""
        assert fields["resumed_at"]
        assert fields["last_recommended_action"] == "RESUME"

    @pytest.mark.asyncio
    async def test_green_tick_sends_resume_alert(self, monkeypatch):
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        nocodb.list_records.side_effect = [
            {"list": [{"Id": i} for i in range(200)]},
            {"list": [{"Id": i} for i in range(20)]},
            {"list": [{"Id": i} for i in range(15)]},
        ]
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        webhook = AsyncMock()
        monkeypatch.setattr(runner, "_send_alert_webhook", webhook)

        await runner.tick(GuardianConfig())
        webhook.assert_awaited_once()
        payload = webhook.await_args.args[0]
        assert payload["resume_outreach"] is True
        assert payload["action"] == "RESUME"
