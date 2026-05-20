"""Tests for the Auto-reply Agent (Adim 6)."""
from __future__ import annotations

import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.auto_reply.policy import AutoReplyConfig  # noqa: E402
from src.agents.auto_reply.targeting import _build_where, find_pending_inbounds  # noqa: E402
from src.agents.auto_reply.templates import FALLBACK_TEMPLATES, has_active_templates  # noqa: E402
from src.agents.auto_reply.responder import (  # noqa: E402
    AutoReplyDecision,
    _build_user_prompt,
    _pick_base_template,
)
from src.agents.auto_reply import runner  # noqa: E402


class TestAutoReplyConfig:
    def test_defaults(self):
        c = AutoReplyConfig()
        assert c.poll_interval_sec == 60
        assert c.reply_min_delay_sec == 30
        assert c.reply_max_delay_sec == 60
        assert c.max_inbound_age_minutes == 60

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("AUTO_REPLY_POLL_SEC", "15")
        monkeypatch.setenv("AUTO_REPLY_MODEL", "gpt-4o")
        c = AutoReplyConfig.from_env()
        assert c.poll_interval_sec == 15
        assert c.model == "gpt-4o"

    def test_jitter_within_bounds(self):
        c = AutoReplyConfig(reply_min_delay_sec=5, reply_max_delay_sec=7)
        for _ in range(20):
            d = c.jitter_delay()
            assert 5 <= d <= 7


class TestTemplates:
    def test_has_active_for_olumlu_and_soru(self):
        assert has_active_templates("olumlu") is True
        assert has_active_templates("soru") is True

    def test_has_none_for_olumsuz_and_spam(self):
        assert has_active_templates("olumsuz") is False
        assert has_active_templates("spam") is False

    def test_itiraz_uses_playbook_not_fallback_pool(self):
        # itiraz cevabi FALLBACK_TEMPLATES'ten degil ITIRAZ_PLAYBOOK'tan
        # anchor alir; bu yuzden FALLBACK_TEMPLATES['itiraz'] bos kalir.
        assert has_active_templates("itiraz") is False

    def test_no_emoji_or_link(self):
        for variants in FALLBACK_TEMPLATES.values():
            for v in variants:
                assert "http" not in v.lower()
                assert "₺" not in v


class TestResponderHelpers:
    def test_build_user_prompt_includes_message(self):
        p = _build_user_prompt("Merhaba ilgileniyorum", "olumlu", "Bir sablon")
        assert "Merhaba ilgileniyorum" in p
        assert "Bir sablon" in p
        assert "olumlu" in p

    def test_build_user_prompt_without_template(self):
        p = _build_user_prompt("Selam", None, None)
        assert "Selam" in p
        assert "Ornek ton" not in p

    def test_pick_base_template_prefers_intent_pool(self):
        rng = random.Random(0)
        t = _pick_base_template(FALLBACK_TEMPLATES, "olumlu", rng=rng)
        assert t in FALLBACK_TEMPLATES["olumlu"]

    def test_pick_base_template_fallback_when_intent_empty(self):
        rng = random.Random(0)
        # 'olumsuz' has empty pool -> fall back to olumlu
        t = _pick_base_template(FALLBACK_TEMPLATES, "olumsuz", rng=rng)
        assert t in FALLBACK_TEMPLATES["olumlu"]

    def test_pick_base_template_none_when_intent_is_none(self):
        # No intent guess + no pool seed -> uses FALLBACK olumlu reservoir
        # (design: always anchor LLM with SOME tone sample).
        t = _pick_base_template(FALLBACK_TEMPLATES, None)
        assert t in FALLBACK_TEMPLATES["olumlu"]


class TestTargeting:
    def test_where_filter_shape(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        w = _build_where(now=now)
        assert "(yon,eq,Gelen)" in w
        assert "(auto_reply_processed,eq,false)" in w
        # NocoDB v2: exactDate operator (datetime SQL format reddediliyor)
        assert "(tarih,gte,exactDate,2026-05-10)" in w

    def test_find_pending_inbounds_returns_fresh_oldest_first(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
        client = MagicMock()
        client.list_records.return_value = {
            "list": [
                {"Id": 1, "tarih": "2026-05-10T10:30:00+00:00"},
                {"Id": 2, "tarih": "2026-05-10T11:15:00+00:00"},
                {"Id": 3, "tarih": "2026-05-10T11:45:00+00:00"},
            ]
        }
        rows = find_pending_inbounds(
            client, "msgs_tbl", batch_size=10, max_age_minutes=60, now=now
        )
        assert [r["Id"] for r in rows] == [2, 3]
        kwargs = client.list_records.call_args.kwargs
        assert kwargs["sort"] == "tarih"

    def test_find_pending_inbounds_empty(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        rows = find_pending_inbounds(
            client, "msgs_tbl", batch_size=10, max_age_minutes=60
        )
        assert rows == []


def _make_decision(intent, reply="", conf=0.9, objection_type=None):
    return AutoReplyDecision(
        intent=intent,
        reply_text=reply,
        confidence=conf,
        objection_type=objection_type,
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
    return nocodb, zernio


class TestHandleOne:
    @pytest.mark.asyncio
    async def test_empty_body_skips_and_marks_processed(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        result = await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "   "},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["skipped"] == "empty"
        nocodb.update_record.assert_called_once_with(
            "msgs_tbl", 7, {"auto_reply_processed": True}
        )
        zernio.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_olumlu_sends_reply_and_promotes_lead(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision("olumlu", "Tesekkurler, ne zaman gorusebiliriz?", 0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "ilgileniyorum", "lead_adi": "Otel A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is True
        assert result["intent"] == "olumlu"

        zernio.send_message.assert_awaited_once_with(
            "conv-1", "Tesekkurler, ne zaman gorusebiliriz?"
        )

        upsert_args = nocodb.upsert_record.call_args.args
        assert upsert_args[0] == "msgs_tbl"
        assert upsert_args[1] == "external_message_id"
        out_fields = upsert_args[2]
        assert out_fields["yon"] == "Giden"
        assert out_fields["tur"] == "Auto Reply"
        assert out_fields["agent"] == "Auto-reply Agent"

        update_calls = nocodb.update_record.call_args_list
        lead_update = next(c for c in update_calls if c.args[0] == "leads_tbl")
        assert lead_update.args[1] == 42
        assert lead_update.args[2]["asama"] == "Takipte"

        msg_update = next(
            c for c in update_calls
            if c.args[0] == "msgs_tbl" and c.args[2].get("auto_reply_processed") is True
        )
        assert msg_update.args[1] == 7

    @pytest.mark.asyncio
    async def test_olumsuz_skips_send_but_marks_processed(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision("olumsuz", "", 0.95)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 8, "mesaj_icerigi": "ilgilenmiyorum", "lead_adi": "Otel B"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is False
        assert result["intent"] == "olumsuz"
        zernio.send_message.assert_not_called()
        nocodb.update_record.assert_called_with(
            "msgs_tbl", 8, {"auto_reply_processed": True}
        )

    @pytest.mark.asyncio
    async def test_low_confidence_does_not_send(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision("olumlu", "Cevap", 0.3)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 9, "mesaj_icerigi": "????", "lead_adi": "Otel C"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is False
        zernio.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_classifies_but_writes_nothing(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision("olumlu", "cevap", 0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 10, "mesaj_icerigi": "evet", "lead_adi": "Otel D"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["reply_sent"] is False
        zernio.send_message.assert_not_called()
        nocodb.update_record.assert_not_called()
        nocodb.upsert_record.assert_not_called()


class TestLoop:
    @pytest.mark.asyncio
    async def test_loop_returns_when_tables_missing(self, monkeypatch):
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
        monkeypatch.delenv("NOCODB_MESSAGES_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        await runner.loop(max_iterations=1)

    @pytest.mark.asyncio
    async def test_loop_sleeps_when_no_inbounds(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        nocodb = MagicMock()
        nocodb.list_records.return_value = {"list": []}
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)

        sleeps: list[float] = []

        async def fake_sleep(s):
            sleeps.append(s)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        await runner.loop(AutoReplyConfig(poll_interval_sec=42), max_iterations=1)
        assert 42 in sleeps


class TestWebhookIntegrationField:
    def test_incoming_message_has_auto_reply_processed_false(self):
        from src.app.zernio_webhook import map_to_message_fields

        payload = {
            "event": "message.received",
            "message": {
                "direction": "incoming",
                "platform": "whatsapp",
                "text": "merhaba",
                "platformMessageId": "wamid.XYZ",
            },
        }
        fields = map_to_message_fields(payload, "Otel X")
        assert fields["auto_reply_processed"] is False
        assert fields["yon"] == "Gelen"


class TestAutoReplyContactTagging:
    @pytest.mark.asyncio
    async def test_tags_contact_when_conversation_has_contact(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        zernio.find_conversation_by_phone = AsyncMock(
            return_value={"id": "conv-1", "contact": {"id": "c-9", "tags": ["bolge_bodrum"]}}
        )
        zernio.tag_contact = AsyncMock(return_value={})

        async def fake_decide(message, **kwargs):
            return _make_decision("olumlu", "Tesekkurler, gorusebilir miyiz?", 0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "ilgileniyorum", "lead_adi": "Otel A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        zernio.tag_contact.assert_awaited_once()
        contact_id, tags = zernio.tag_contact.await_args.args
        assert contact_id == "c-9"
        assert set(tags) == {"bolge_bodrum", "hot_lead", "oto_yanit_gonderildi"}

    @pytest.mark.asyncio
    async def test_skips_tag_when_no_contact_in_conversation(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        zernio.find_conversation_by_phone = AsyncMock(return_value={"id": "conv-1"})
        zernio.tag_contact = AsyncMock(return_value={})

        async def fake_decide(message, **kwargs):
            return _make_decision("olumlu", "Tesekkurler", 0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "evet", "lead_adi": "Otel A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        zernio.tag_contact.assert_not_called()


class TestFallbackTemplatesFromSeyma:
    def test_olumlu_contains_seyma_anchors(self):
        joined = " ".join(FALLBACK_TEMPLATES["olumlu"])
        assert "Bodrum" in joined
        assert "Marmaris" in joined
        assert "Fethiye" in joined
        assert "Booking" in joined
        assert "30 dakika" in joined


class TestItirazAutoReply:
    @pytest.mark.asyncio
    async def test_itiraz_intent_sends_reply_and_sets_asama(self, mock_clients, monkeypatch):
        """intent=itiraz: cevap dogrudan gonderilir, asama->Itiraz,
        'Itiraz Yanit' loglanir (insan onayi / n8n handoff yok)."""
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision(
                "itiraz", "Butce tarafini anliyorum, gorusebilir miyiz?",
                0.9, objection_type="fiyat",
            )

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={
                "Id": 7,
                "mesaj_icerigi": "Fiyatınız çok yüksek, indirim olur mu?",
                "lead_adi": "Otel A",
            },
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )

        assert result["reply_sent"] is True
        assert result["intent"] == "itiraz"
        assert result["objection_type"] == "fiyat"
        zernio.send_message.assert_awaited_once_with(
            "conv-1", "Butce tarafini anliyorum, gorusebilir miyiz?"
        )

        out_fields = nocodb.upsert_record.call_args.args[2]
        assert out_fields["tur"] == "Itiraz Yanit"
        assert out_fields["yon"] == "Giden"

        lead_update = next(
            c for c in nocodb.update_record.call_args_list
            if c.args[0] == "leads_tbl"
        )
        assert lead_update.args[2]["asama"] == "Itiraz"

    @pytest.mark.asyncio
    async def test_itiraz_low_confidence_no_send(self, mock_clients, monkeypatch):
        """conf < 0.5 ise sessiz kal — gonderim yok."""
        nocodb, zernio = mock_clients

        async def fake_decide(message, **kwargs):
            return _make_decision("itiraz", "taslak", 0.3, objection_type="fiyat")

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 8, "mesaj_icerigi": "?", "lead_adi": "Otel B"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        assert result["reply_sent"] is False
        zernio.send_message.assert_not_called()
        nocodb.update_record.assert_called_with(
            "msgs_tbl", 8, {"auto_reply_processed": True}
        )
