"""Tests for the Outreach Agent (Adim 4).

Covers:
- OutreachConfig.from_env (defaults + env override)
- OutreachPolicy: business hours, daily limit, batch break logic, jitter range
- pick_next_target: where filter shape, oldest-first, empty queue
- send_one: dry-run skips IO, real send writes lead update + Etkilesimler log
- runner.loop: skips when off-hours, exits cleanly with max_iterations
- send_whatsapp_template tool: phone+template validation, Zernio call shape
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.outreach.policy import OutreachConfig, OutreachPolicy  # noqa: E402
from src.agents.outreach.targeting import (  # noqa: E402
    _build_where,
    count_sent_today,
    pick_next_target,
)
from src.agents.outreach import runner  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestOutreachConfig:
    def test_defaults(self):
        cfg = OutreachConfig()
        assert cfg.timezone == "Europe/Istanbul"
        assert cfg.hour_start == 9
        assert cfg.hour_end == 21
        assert cfg.daily_limit == 240
        assert cfg.template_name == "ege_otel_yaz_sezon_v1"
        assert cfg.source_workflow_id == "outreach_agent_v1"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("OUTREACH_DAILY_LIMIT", "50")
        monkeypatch.setenv("OUTREACH_HOUR_START", "10")
        monkeypatch.setenv("OUTREACH_TEMPLATE_NAME", "test_template_v2")
        cfg = OutreachConfig.from_env()
        assert cfg.daily_limit == 50
        assert cfg.hour_start == 10
        assert cfg.template_name == "test_template_v2"

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("OUTREACH_DAILY_LIMIT", "not-a-number")
        cfg = OutreachConfig.from_env()
        assert cfg.daily_limit == 240


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def _utc(hour: int, minute: int = 0) -> datetime:
    """UTC time which, in Istanbul (UTC+3), corresponds to (hour, minute) local."""
    # naive: TR is UTC+3 year-round. ZoneInfo handles DST if any.
    return datetime(2026, 5, 9, hour - 3, minute, tzinfo=timezone.utc)


class TestPolicyBusinessHours:
    def test_inside_window(self):
        p = OutreachPolicy(OutreachConfig())
        assert p.within_business_hours(_utc(9, 30)) is True
        assert p.within_business_hours(_utc(20, 59)) is True

    def test_outside_window(self):
        p = OutreachPolicy(OutreachConfig())
        assert p.within_business_hours(_utc(8, 59)) is False
        assert p.within_business_hours(_utc(21, 0)) is False
        assert p.within_business_hours(_utc(3, 0)) is False


class TestPolicyDailyLimit:
    def test_under_limit_initially(self):
        p = OutreachPolicy(OutreachConfig(daily_limit=3))
        assert p.under_daily_limit() is True

    def test_record_send_increments(self):
        p = OutreachPolicy(OutreachConfig(daily_limit=2))
        p.record_send()
        assert p.under_daily_limit() is True
        p.record_send()
        assert p.under_daily_limit() is False

    def test_reset_daily_zeroes_count(self):
        p = OutreachPolicy(OutreachConfig(daily_limit=2))
        p.record_send()
        p.record_send()
        p.reset_daily()
        assert p.under_daily_limit() is True

    def test_is_eligible_combines_hours_and_limit(self):
        p = OutreachPolicy(OutreachConfig(daily_limit=1))
        ok, reason = p.is_eligible(_utc(10))
        assert ok and reason == "ok"
        p.record_send()
        ok, reason = p.is_eligible(_utc(10))
        assert not ok and reason == "daily limit reached"
        ok, reason = p.is_eligible(_utc(8))  # before-hours wins
        assert not ok and reason == "outside business hours"


class TestPolicyPacing:
    def test_jitter_within_bounds(self):
        p = OutreachPolicy(OutreachConfig(min_delay_sec=10, max_delay_sec=20))
        for _ in range(20):
            d = p.next_delay_sec()
            assert 10 <= d <= 20

    def test_batch_break_after_n_sends(self):
        p = OutreachPolicy(OutreachConfig(batch_size=3))
        assert p.should_take_batch_break() is False
        p.record_send()
        p.record_send()
        assert p.should_take_batch_break() is False
        p.record_send()
        assert p.should_take_batch_break() is True


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------


class TestTargeting:
    def test_where_filter_shape(self):
        where = _build_where("outreach_agent_v1")
        assert "(source_workflow_id,eq,outreach_agent_v1)" in where
        assert "(asama,eq,Yeni)" in where
        assert "(telefon,notblank)" in where
        assert "~and" in where

    def test_pick_next_returns_first_row(self):
        client = MagicMock()
        client.list_records.return_value = {
            "list": [{"Id": 1, "ad_soyad": "Otel A"}, {"Id": 2}],
        }
        target = pick_next_target(client, "leads_tbl", "outreach_agent_v1")
        assert target == {"Id": 1, "ad_soyad": "Otel A"}
        kwargs = client.list_records.call_args.kwargs
        assert kwargs["limit"] == 1
        assert kwargs["sort"] == "CreatedAt"

    def test_pick_next_returns_none_when_empty(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        assert pick_next_target(client, "leads_tbl", "outreach_agent_v1") is None


# ---------------------------------------------------------------------------
# send_one
# ---------------------------------------------------------------------------


class TestSendOne:
    @pytest.mark.asyncio
    async def test_dry_run_skips_zernio_and_nocodb(self, monkeypatch):
        zernio_mock = MagicMock()
        nocodb_mock = MagicMock()
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio_mock)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb_mock)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=OutreachConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["lead_id"] == 7
        zernio_mock.send_template.assert_not_called()
        nocodb_mock.update_record.assert_not_called()
        nocodb_mock.upsert_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_send_writes_lead_update_and_etkilesimler(self, monkeypatch):
        zernio_mock = MagicMock()
        zernio_mock.send_template = AsyncMock(return_value={"messageId": "wamid.X"})
        nocodb_mock = MagicMock()
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio_mock)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb_mock)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=OutreachConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["success"] is True

        # Zernio called with template + variables=[name]
        send_kwargs = zernio_mock.send_template.await_args.kwargs
        assert send_kwargs["phone"] == "+905551112233"
        assert send_kwargs["template_name"] == "ege_otel_yaz_sezon_v1"
        assert send_kwargs["variables"] == ["Otel A"]

        # Lead -> Soguk + notlar appended
        update_call = nocodb_mock.update_record.call_args
        assert update_call.args[0] == "leads_tbl"
        assert update_call.args[1] == 7
        fields = update_call.args[2]
        assert fields["asama"] == "Soguk"
        assert "Cold outreach" in fields["notlar"]

        # Etkilesimler upsert keyed by external_message_id
        upsert_call = nocodb_mock.upsert_record.call_args
        assert upsert_call.args[0] == "msgs_tbl"
        assert upsert_call.args[1] == "external_message_id"
        msg_fields = upsert_call.args[2]
        assert msg_fields["yon"] == "Giden"
        assert msg_fields["tur"] == "Ilk Mesaj"
        assert msg_fields["external_message_id"] == "wamid.X"

    @pytest.mark.asyncio
    async def test_etkilesimler_failure_is_swallowed(self, monkeypatch):
        zernio_mock = MagicMock()
        zernio_mock.send_template = AsyncMock(return_value={})
        nocodb_mock = MagicMock()
        nocodb_mock.upsert_record.side_effect = RuntimeError("Etkilesimler down")
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio_mock)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb_mock)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=OutreachConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        # Lead update happened; Etkilesimler swallowed
        assert result["success"] is True
        nocodb_mock.update_record.assert_called_once()


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------


class TestLoop:
    @pytest.mark.asyncio
    async def test_loop_returns_immediately_when_no_leads_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        # Should log & return without crashing
        await runner.loop(max_iterations=1)

    @pytest.mark.asyncio
    async def test_loop_pauses_when_off_hours(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        # Force "outside business hours"
        monkeypatch.setattr(
            OutreachPolicy, "within_business_hours", lambda self, now=None: False
        )
        sleeps: list[float] = []

        async def fake_sleep(secs):
            sleeps.append(secs)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await runner.loop(max_iterations=1)
        assert sleeps and sleeps[0] == 300

    @pytest.mark.asyncio
    async def test_loop_picks_target_and_records_send(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        monkeypatch.setenv("DRY_RUN", "true")  # safe path, no real Zernio
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb_mock = MagicMock()
        nocodb_mock.list_records.return_value = {
            "list": [{"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"}]
        }
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb_mock)
        monkeypatch.setattr(runner, "get_zernio_client", lambda: MagicMock())

        # Skip real sleeps
        async def fake_sleep(secs):
            pass

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        # Force "in business hours"
        monkeypatch.setattr(
            OutreachPolicy, "within_business_hours", lambda self, now=None: True
        )

        await runner.loop(max_iterations=1)
        assert nocodb_mock.list_records.call_count == 1


# ---------------------------------------------------------------------------
# send_whatsapp_template tool
# ---------------------------------------------------------------------------


class TestSendWhatsappTemplateTool:
    @pytest.mark.asyncio
    async def test_happy_path(self, monkeypatch):
        from src.tools.sales import zernio_tools as zt

        client = MagicMock()
        client.send_template = AsyncMock(return_value={"messageId": "wamid.Z"})
        monkeypatch.setattr(zt, "_get_client", lambda: client)

        result = await zt._send_whatsapp_template_impl(
            phone="+905551112233",
            template_name="ege_otel_yaz_sezon_v1",
            variables=["Otel Adi"],
        )
        assert result["success"] is True
        assert result["template"] == "ege_otel_yaz_sezon_v1"
        kwargs = client.send_template.await_args.kwargs
        assert kwargs["phone"] == "+905551112233"
        assert kwargs["variables"] == ["Otel Adi"]
        assert kwargs["language"] == "tr"

    @pytest.mark.asyncio
    async def test_rejects_empty_phone(self, monkeypatch):
        from src.tools.sales import zernio_tools as zt
        monkeypatch.setattr(zt, "_get_client", lambda: MagicMock())
        result = await zt._send_whatsapp_template_impl(
            phone="", template_name="t", variables=[]
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_rejects_empty_template(self, monkeypatch):
        from src.tools.sales import zernio_tools as zt
        monkeypatch.setattr(zt, "_get_client", lambda: MagicMock())
        result = await zt._send_whatsapp_template_impl(
            phone="+90...", template_name="", variables=[]
        )
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    def test_tool_registered_in_get_zernio_tools(self):
        from src.tools.sales.zernio_tools import get_zernio_tools

        names = {t.name for t in get_zernio_tools()}
        assert "send_whatsapp_template" in names
        assert names == {
            "list_contacts",
            "find_conversation",
            "send_message",
            "send_whatsapp_template",
            "tag_contact",
        }


# ---------------------------------------------------------------------------
# Adim 7 fix-1: Daily limit persistence (count_sent_today)
# ---------------------------------------------------------------------------


class TestCountSentToday:
    def test_where_filter_uses_utc_midnight(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        now = datetime(2026, 5, 11, 14, 23, tzinfo=timezone.utc)
        count_sent_today(client, "msgs_tbl", now=now)
        where = client.list_records.call_args.kwargs["where"]
        assert "(yon,eq,Giden)" in where
        assert "(agent,eq,Outreach Agent)" in where
        assert "(tarih,ge,2026-05-11T00:00:00Z)" in where

    def test_returns_row_count(self):
        client = MagicMock()
        client.list_records.return_value = {
            "list": [{"Id": 1}, {"Id": 2}, {"Id": 3}]
        }
        assert count_sent_today(client, "msgs_tbl") == 3

    def test_empty_means_zero(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        assert count_sent_today(client, "msgs_tbl") == 0


# ---------------------------------------------------------------------------
# Adim 7 fix-2: send_with_retry
# ---------------------------------------------------------------------------


class TestSendWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, monkeypatch):
        zernio = MagicMock()
        zernio.send_template = AsyncMock(return_value={"messageId": "ok"})
        # No sleep needed when first attempt wins
        monkeypatch.setattr(runner.asyncio, "sleep", AsyncMock())

        result = await runner._send_with_retry(
            zernio, phone="+9", template_name="t", variables=["x"],
            language="tr", retries=2, retry_delay_sec=30,
        )
        assert result == {"messageId": "ok"}
        assert zernio.send_template.await_count == 1

    @pytest.mark.asyncio
    async def test_recovers_on_second_attempt(self, monkeypatch):
        zernio = MagicMock()
        zernio.send_template = AsyncMock(
            side_effect=[RuntimeError("boom"), {"messageId": "ok"}]
        )
        sleeps = []

        async def fake_sleep(s):
            sleeps.append(s)

        monkeypatch.setattr(runner.asyncio, "sleep", fake_sleep)

        result = await runner._send_with_retry(
            zernio, phone="+9", template_name="t", variables=["x"],
            language="tr", retries=2, retry_delay_sec=30,
        )
        assert result == {"messageId": "ok"}
        assert zernio.send_template.await_count == 2
        assert sleeps == [30]

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_fail(self, monkeypatch):
        zernio = MagicMock()
        zernio.send_template = AsyncMock(
            side_effect=[RuntimeError("a"), RuntimeError("b"), RuntimeError("c")]
        )
        monkeypatch.setattr(runner.asyncio, "sleep", AsyncMock())

        with pytest.raises(RuntimeError, match="c"):
            await runner._send_with_retry(
                zernio, phone="+9", template_name="t", variables=["x"],
                language="tr", retries=2, retry_delay_sec=30,
            )
        # 1 initial + 2 retries = 3 attempts
        assert zernio.send_template.await_count == 3


# ---------------------------------------------------------------------------
# Adim 7 fix-3: Zernio contact tagging
# ---------------------------------------------------------------------------


class TestTagZernioContact:
    @pytest.mark.asyncio
    async def test_merges_into_existing_tags(self):
        zernio = MagicMock()
        zernio.list_contacts = AsyncMock(return_value={
            "contacts": [
                {"id": "c1", "phone": "+90 555 111 22 33", "tags": ["bolge_bodrum"]}
            ]
        })
        zernio.tag_contact = AsyncMock(return_value={})

        await runner._tag_zernio_contact(
            zernio, "+905551112233", to_add=["kontak_atildi", "outreach_v1"]
        )
        zernio.tag_contact.assert_awaited_once()
        contact_id, tags = zernio.tag_contact.await_args.args
        assert contact_id == "c1"
        assert set(tags) == {"bolge_bodrum", "kontak_atildi", "outreach_v1"}

    @pytest.mark.asyncio
    async def test_skips_when_no_match(self):
        zernio = MagicMock()
        zernio.list_contacts = AsyncMock(return_value={"contacts": []})
        zernio.tag_contact = AsyncMock()

        await runner._tag_zernio_contact(zernio, "+905551112233", to_add=["x"])
        zernio.tag_contact.assert_not_called()

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        zernio = MagicMock()
        zernio.list_contacts = AsyncMock(side_effect=RuntimeError("zernio down"))
        # Should not raise
        await runner._tag_zernio_contact(zernio, "+905551112233", to_add=["x"])

    @pytest.mark.asyncio
    async def test_skips_when_phone_empty(self):
        zernio = MagicMock()
        zernio.list_contacts = AsyncMock()
        await runner._tag_zernio_contact(zernio, "", to_add=["x"])
        zernio.list_contacts.assert_not_called()


class TestSendOneInvokesTagging:
    @pytest.mark.asyncio
    async def test_real_send_calls_tag_zernio_contact(self, monkeypatch):
        zernio_mock = MagicMock()
        zernio_mock.send_template = AsyncMock(return_value={"messageId": "wamid.X"})
        zernio_mock.list_contacts = AsyncMock(return_value={
            "contacts": [{"id": "c1", "phone": "+905551112233", "tags": []}]
        })
        zernio_mock.tag_contact = AsyncMock(return_value={})
        nocodb_mock = MagicMock()
        monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio_mock)
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb_mock)

        result = await runner.send_one(
            lead={"Id": 7, "ad_soyad": "Otel A", "telefon": "+905551112233"},
            config=OutreachConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["success"] is True
        zernio_mock.tag_contact.assert_awaited_once()
        _, tags = zernio_mock.tag_contact.await_args.args
        assert "kontak_atildi" in tags
        assert "outreach_v1" in tags
