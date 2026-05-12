"""Tests for Guardian (Bekci Robot, Adim 8)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.guardian.decisions import Decision, DecisionLevel, decide  # noqa: E402
from src.agents.guardian.metrics import GuardianMetrics, compute_metrics  # noqa: E402
from src.agents.guardian.policy import GuardianConfig  # noqa: E402
from src.agents.guardian import runner  # noqa: E402


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestGuardianConfig:
    def test_defaults(self):
        c = GuardianConfig()
        assert c.poll_interval_sec == 1800
        assert c.window_hours == 24
        assert c.reply_rate_red_pct == 3.0
        assert c.reply_rate_yellow_pct == 5.0
        assert c.min_outreach_for_eval == 50

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GUARDIAN_REPLY_RED", "2.5")
        monkeypatch.setenv("GUARDIAN_MIN_OUTREACH", "100")
        c = GuardianConfig.from_env()
        assert c.reply_rate_red_pct == 2.5
        assert c.min_outreach_for_eval == 100


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestGuardianMetrics:
    def test_reply_rate_pct(self):
        m = GuardianMetrics(window_hours=24, outreach_sent=200, inbound_received=10,
                            auto_replies_sent=8, outreach_failed=0)
        assert m.reply_rate_pct == 5.0

    def test_zero_outreach_no_division_error(self):
        m = GuardianMetrics(24, 0, 0, 0, 0)
        assert m.reply_rate_pct == 0.0
        assert m.engagement_rate_pct == 0.0
        assert m.failure_rate_pct == 0.0

    def test_engagement_rate(self):
        m = GuardianMetrics(24, 200, 10, 6, 0)
        assert m.engagement_rate_pct == 60.0

    def test_failure_rate(self):
        m = GuardianMetrics(24, 95, 0, 0, 5)
        assert m.failure_rate_pct == 5.0

    def test_to_dict_includes_derived(self):
        m = GuardianMetrics(24, 100, 5, 3, 0)
        d = m.to_dict()
        assert d["reply_rate_pct"] == 5.0
        assert d["engagement_rate_pct"] == 60.0


class TestComputeMetrics:
    def test_uses_correct_filters(self):
        client = MagicMock()
        # Each call returns different list -> exercise where filter routing
        side_effects = [
            {"list": [{"Id": i} for i in range(123)]},  # outreach sent
            {"list": [{"Id": i} for i in range(45)]},   # inbound
            {"list": [{"Id": i} for i in range(30)]},   # auto-reply sent
        ]
        client.list_records.side_effect = side_effects

        now = datetime(2026, 5, 11, 18, 0, tzinfo=timezone.utc)
        m = compute_metrics(client, "msgs_tbl", window_hours=24, now=now)
        assert m.outreach_sent == 123
        assert m.inbound_received == 45
        assert m.auto_replies_sent == 30
        assert m.outreach_failed == 0

        wheres = [c.kwargs["where"] for c in client.list_records.call_args_list]
        # since cutoff = 2026-05-10T18:00:00+00:00
        assert all("2026-05-10 18:00:00" in w for w in wheres)
        assert any("(agent,eq,Outreach Agent)" in w for w in wheres)
        assert any("(yon,eq,Gelen)" in w for w in wheres)
        assert any("(agent,eq,Auto-reply Agent)" in w for w in wheres)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def _metrics(out=200, inb=10, auto=6, fail=0):
    return GuardianMetrics(24, out, inb, auto, fail)


class TestDecide:
    def test_insufficient_when_below_min_outreach(self):
        d = decide(_metrics(out=10), GuardianConfig())
        assert d.level == DecisionLevel.INSUFFICIENT
        assert d.pause_outreach is False

    def test_green_with_healthy_metrics(self):
        # 200 sent, 20 inbound (10%), 12 auto (60%) -> all green
        d = decide(_metrics(out=200, inb=20, auto=12), GuardianConfig())
        assert d.level == DecisionLevel.GREEN
        assert d.pause_outreach is False
        assert d.reasons == []

    def test_yellow_when_reply_rate_below_yellow_above_red(self):
        # 200 sent, 8 inbound (4%) -> below yellow 5%, above red 3%
        d = decide(_metrics(out=200, inb=8, auto=5), GuardianConfig())
        assert d.level == DecisionLevel.YELLOW
        assert d.pause_outreach is False
        assert any("reply_rate" in r for r in d.reasons)

    def test_red_when_reply_rate_below_red(self):
        # 200 sent, 4 inbound (2%) -> below red 3%
        d = decide(_metrics(out=200, inb=4, auto=3), GuardianConfig())
        assert d.level == DecisionLevel.RED
        assert d.pause_outreach is True
        assert any("reply_rate" in r for r in d.reasons)

    def test_red_when_engagement_rate_critical(self):
        # 200 sent, 20 inbound (10% reply ok), 2 auto (10% engagement) -> red
        d = decide(_metrics(out=200, inb=20, auto=2), GuardianConfig())
        assert d.level == DecisionLevel.RED
        assert d.pause_outreach is True
        assert any("engagement_rate" in r for r in d.reasons)

    def test_engagement_rate_skipped_when_inbound_tiny(self):
        # 200 sent, 3 inbound (small sample) — engagement rate not evaluated
        d = decide(_metrics(out=200, inb=3, auto=0), GuardianConfig())
        # Reply rate 1.5% triggers RED on its own
        assert d.level == DecisionLevel.RED
        assert all("engagement_rate" not in r for r in d.reasons)


# ---------------------------------------------------------------------------
# Runner.tick
# ---------------------------------------------------------------------------


class TestRunnerTick:
    @pytest.mark.asyncio
    async def test_persists_health_check_when_settings_table_set(self, monkeypatch):
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        nocodb.list_records.side_effect = [
            {"list": [{"Id": i} for i in range(200)]},  # outreach
            {"list": [{"Id": i} for i in range(20)]},   # inbound
            {"list": [{"Id": i} for i in range(15)]},   # auto-reply
        ]
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(runner, "_send_alert_webhook", AsyncMock())

        result = await runner.tick(GuardianConfig())
        assert result["ok"] is True
        assert result["level"] == "GREEN"

        # Update was called on settings table with metric/decision payload
        update_call = nocodb.update_record.call_args
        assert update_call.args[0] == "settings_tbl"
        assert update_call.args[1] == 1  # single-row pattern
        fields = update_call.args[2]
        assert fields["last_decision_level"] == "GREEN"
        assert "last_metrics_json" in fields

    @pytest.mark.asyncio
    async def test_red_decision_sets_pause_fields_and_alerts(self, monkeypatch):
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        monkeypatch.setenv("GUARDIAN_ALERT_WEBHOOK_URL", "https://n8n.example/webhook/bekci")
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        # Bad outreach rate: 200 sent, 4 inbound -> RED
        nocodb.list_records.side_effect = [
            {"list": [{"Id": i} for i in range(200)]},
            {"list": [{"Id": i} for i in range(4)]},
            {"list": [{"Id": i} for i in range(2)]},
        ]
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        webhook_mock = AsyncMock()
        monkeypatch.setattr(runner, "_send_alert_webhook", webhook_mock)

        result = await runner.tick(GuardianConfig())
        assert result["level"] == "RED"

        fields = nocodb.update_record.call_args.args[2]
        assert fields["outreach_paused"] is True
        assert "reply_rate" in fields["pause_reason"]
        assert fields["paused_at"]

        webhook_mock.assert_awaited_once()
        payload = webhook_mock.await_args.args[0]
        assert payload["level"] == "RED"
        assert payload["pause_outreach"] is True

    @pytest.mark.asyncio
    async def test_skips_persist_when_settings_table_missing(self, monkeypatch):
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        nocodb.list_records.side_effect = [
            {"list": [{"Id": i} for i in range(200)]},
            {"list": [{"Id": i} for i in range(20)]},
            {"list": [{"Id": i} for i in range(15)]},
        ]
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(runner, "_send_alert_webhook", AsyncMock())

        result = await runner.tick(GuardianConfig())
        assert result["ok"] is True
        # No NocoDB write attempted since settings table not configured
        nocodb.update_record.assert_not_called()


# ---------------------------------------------------------------------------
# Outreach pause-flag check
# ---------------------------------------------------------------------------


class TestOutreachPauseCheck:
    def test_returns_false_when_settings_table_not_configured(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        from src.agents.outreach import runner as outreach_runner
        assert outreach_runner._is_outreach_paused() is False

    def test_returns_true_when_paused_flag_set(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.agents.outreach import runner as outreach_runner

        nocodb = MagicMock()
        nocodb.list_records.return_value = {"list": [{"outreach_paused": True}]}
        monkeypatch.setattr(outreach_runner, "get_nocodb_client", lambda: nocodb)

        assert outreach_runner._is_outreach_paused() is True

    def test_returns_false_when_paused_flag_unset(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.agents.outreach import runner as outreach_runner

        nocodb = MagicMock()
        nocodb.list_records.return_value = {"list": [{"outreach_paused": False}]}
        monkeypatch.setattr(outreach_runner, "get_nocodb_client", lambda: nocodb)

        assert outreach_runner._is_outreach_paused() is False

    def test_returns_false_on_nocodb_error(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
        from src.agents.outreach import runner as outreach_runner

        nocodb = MagicMock()
        nocodb.list_records.side_effect = RuntimeError("nocodb down")
        monkeypatch.setattr(outreach_runner, "get_nocodb_client", lambda: nocodb)

        # Fail-open: rather block outreach for non-existent reason than stall
        # forever; metric-based evaluation will catch real issues.
        assert outreach_runner._is_outreach_paused() is False
