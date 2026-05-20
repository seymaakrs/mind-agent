"""Followup Agent testleri."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.followup.policy import FollowupConfig, FollowupPolicy  # noqa: E402
from src.agents.followup.targeting import (  # noqa: E402
    _FOLLOWUP_MARKER,
    _build_where,
    count_sent_today,
    find_followup_targets,
)
from src.agents.followup import runner  # noqa: E402


class TestFollowupConfig:
    def test_defaults(self):
        c = FollowupConfig()
        assert c.hour_start == 10
        assert c.hour_end == 20
        assert c.daily_limit == 80
        assert c.days_since_outreach == 3
        assert c.template_name == "ege_otel_takip_v1"
        assert c.source_workflow_id == "outreach_agent_v1"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("FOLLOWUP_DAILY_LIMIT", "50")
        monkeypatch.setenv("FOLLOWUP_DAYS", "5")
        monkeypatch.setenv("FOLLOWUP_TEMPLATE_NAME", "takip_v2")
        c = FollowupConfig.from_env()
        assert c.daily_limit == 50
        assert c.days_since_outreach == 5
        assert c.template_name == "takip_v2"


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 9, hour - 3, minute, tzinfo=timezone.utc)


class TestFollowupPolicy:
    def test_business_hours(self):
        p = FollowupPolicy(FollowupConfig())
        assert p.within_business_hours(_utc(10, 30)) is True
        assert p.within_business_hours(_utc(9, 30)) is False  # 10 oncesi
        assert p.within_business_hours(_utc(20, 0)) is False  # 20 dahil degil

    def test_daily_limit(self):
        p = FollowupPolicy(FollowupConfig(daily_limit=2))
        assert p.under_daily_limit() is True
        p.record_send()
        p.record_send()
        assert p.under_daily_limit() is False

    def test_jitter_bounds(self):
        p = FollowupPolicy(FollowupConfig(min_delay_sec=10, max_delay_sec=20))
        for _ in range(20):
            d = p.next_delay_sec()
            assert 10 <= d <= 20

    def test_batch_break(self):
        p = FollowupPolicy(FollowupConfig(batch_size=2))
        assert p.should_take_batch_break() is False
        p.record_send()
        assert p.should_take_batch_break() is False
        p.record_send()
        assert p.should_take_batch_break() is True


class TestTargeting:
    def test_where_filter_shape(self):
        cutoff = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        where = _build_where("outreach_agent_v1", cutoff)
        assert "(source_workflow_id,eq,outreach_agent_v1)" in where
        assert "(asama,eq,Soguk)" in where
        assert "(son_temas,lt,exactDate,2026-05-11)" in where

    def test_skips_already_followed_up(self):
        client = MagicMock()
        client.list_records.return_value = {
            "list": [
                {"Id": 1, "notlar": f"foo\n[date] {_FOLLOWUP_MARKER}"},
                {"Id": 2, "notlar": "henuz hicbir sey"},
            ]
        }
        targets = find_followup_targets(client, "leads_tbl", "outreach_agent_v1")
        assert [t["Id"] for t in targets] == [2]

    def test_returns_empty_when_no_candidates(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        assert find_followup_targets(client, "leads_tbl", "x") == []

    def test_nocodb_error_returns_empty(self):
        client = MagicMock()
        client.list_records.side_effect = RuntimeError("nocodb down")
        assert find_followup_targets(client, "leads_tbl", "x") == []

    def test_sort_oldest_son_temas_first(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        find_followup_targets(client, "leads_tbl", "outreach_agent_v1")
        kwargs = client.list_records.call_args.kwargs
        assert kwargs["sort"] == "son_temas"


class TestCountSentToday:
    def test_where_filter_includes_agent(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        now = datetime(2026, 5, 11, 14, 0, tzinfo=timezone.utc)
        count_sent_today(client, "msgs_tbl", now=now)
        where = client.list_records.call_args.kwargs["where"]
        assert "(yon,eq,Giden)" in where
        assert "(agent,eq,Followup Agent)" in where
        assert "exactDate,2026-05-11" in where

    def test_returns_row_count(self):
        client = MagicMock()
        client.list_records.return_value = {"list": [{"Id": i} for i in range(7)]}
        assert count_sent_today(client, "msgs_tbl") == 7


class TestSendOne:
    @pytest.mark.asyncio
    async def test_dry_run_skips_io(self, monkeypatch):
        zernio = MagicMock()
        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=FollowupConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=True,
        )
        assert result["dry_run"] is True
        zernio.send_template.assert_not_called()
        nocodb.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_send_writes_takip_marker_and_log(self, monkeypatch):
        zernio = MagicMock()
        zernio.send_template = AsyncMock(return_value={"messageId": "wamid.T"})
        zernio.list_contacts = AsyncMock(return_value={
            "contacts": [{"id": "c1", "phone": "+905551112233", "tags": []}]
        })
        zernio.tag_contact = AsyncMock(return_value={})
        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=FollowupConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["success"] is True

        send_kwargs = zernio.send_template.await_args.kwargs
        assert send_kwargs["template_name"] == "ege_otel_takip_v1"
        assert send_kwargs["variables"] == ["Otel A"]

        # Lead update: asama=Takipte + notlar'a Takip gonderildi isareti
        update_call = nocodb.update_record.call_args
        fields = update_call.args[2]
        assert fields["asama"] == "Takipte"
        assert _FOLLOWUP_MARKER in fields["notlar"]

        # Etkilesimler upsert: tur=Takip, agent=Followup Agent
        upsert_call = nocodb.upsert_record.call_args
        msg_fields = upsert_call.args[2]
        assert msg_fields["tur"] == "Takip"
        assert msg_fields["agent"] == "Followup Agent"
        assert msg_fields["yon"] == "Giden"

        # Zernio contact tagged
        zernio.tag_contact.assert_awaited_once()
        _, tags = zernio.tag_contact.await_args.args
        assert "takip_atildi" in tags


class TestPauseCheck:
    def test_returns_false_when_settings_table_unset(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        assert runner._is_outreach_paused() is False

    def test_returns_true_when_paused(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings")
        nocodb = MagicMock()
        nocodb.list_records.return_value = {"list": [{"outreach_paused": True}]}
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        assert runner._is_outreach_paused() is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings")
        nocodb = MagicMock()
        nocodb.list_records.side_effect = RuntimeError("boom")
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        assert runner._is_outreach_paused() is False


class TestLoop:
    @pytest.mark.asyncio
    async def test_returns_when_no_leads_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        await runner.loop(max_iterations=1)

    @pytest.mark.asyncio
    async def test_sleeps_when_off_hours(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        monkeypatch.setattr(
            FollowupPolicy, "within_business_hours", lambda self, now=None: False
        )
        sleeps: list[float] = []

        async def fake_sleep(secs):
            sleeps.append(secs)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await runner.loop(max_iterations=1)
        assert sleeps and sleeps[0] == 600
