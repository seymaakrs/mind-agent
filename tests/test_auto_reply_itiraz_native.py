"""Faz 1 — Auto-reply native itiraz oneri taslagi.

Kapsam:
- responder: objection_type alani + playbook anchor prompt'a giriyor
- templates: ITIRAZ_PLAYBOOK saglikli (link/fiyat yok)
- runner: AUTO_REPLY_ITIRAZ_NATIVE flag kapali/acik davranisi
  (musteriye OTOMATIK yanit hicbir kosulda gitmez)
"""
from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.auto_reply.policy import AutoReplyConfig  # noqa: E402
from src.agents.auto_reply.responder import (  # noqa: E402
    AutoReplyDecision,
    _build_user_prompt,
    _format_playbook,
)
from src.agents.auto_reply.templates import (  # noqa: E402
    ITIRAZ_PLAYBOOK,
    has_objection_playbook,
)
from src.agents.auto_reply import runner  # noqa: E402


class TestItirazPlaybook:
    def test_all_objection_types_present(self):
        assert set(ITIRAZ_PLAYBOOK) == {
            "fiyat",
            "rekabet",
            "erteleme",
            "olcek",
            "teknoloji",
            "kanit",
        }

    def test_each_type_has_anchors(self):
        for anchors in ITIRAZ_PLAYBOOK.values():
            assert len(anchors) >= 2

    def test_no_link_or_price(self):
        for anchors in ITIRAZ_PLAYBOOK.values():
            for a in anchors:
                assert "http" not in a.lower()
                assert "₺" not in a

    def test_keeps_seyma_anchors(self):
        joined = " ".join(a for v in ITIRAZ_PLAYBOOK.values() for a in v)
        assert "30 dakika" in joined
        assert "Bodrum" in joined

    def test_has_objection_playbook_helper(self):
        assert has_objection_playbook("fiyat") is True
        assert has_objection_playbook("yok") is False


class TestResponderObjection:
    def test_decision_objection_type_defaults_none(self):
        d = AutoReplyDecision(intent="olumlu", reply_text="x", confidence=0.9)
        assert d.objection_type is None

    def test_decision_accepts_objection_type(self):
        d = AutoReplyDecision(
            intent="itiraz",
            reply_text="taslak",
            confidence=0.8,
            objection_type="fiyat",
        )
        assert d.objection_type == "fiyat"

    def test_format_playbook_compact(self):
        txt = _format_playbook(ITIRAZ_PLAYBOOK)
        assert txt is not None
        assert "[fiyat]" in txt and "[kanit]" in txt

    def test_format_playbook_none_when_empty(self):
        assert _format_playbook(None) is None
        assert _format_playbook({}) is None

    def test_build_user_prompt_includes_playbook(self):
        p = _build_user_prompt(
            "Fiyat çok yüksek", "itiraz", "anchor", playbook=ITIRAZ_PLAYBOOK
        )
        assert "ITIRAZ OYUN KITABI" in p
        assert "[fiyat]" in p

    def test_build_user_prompt_without_playbook(self):
        p = _build_user_prompt("Selam", None, None)
        assert "ITIRAZ OYUN KITABI" not in p


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


def _itiraz_decision():
    return AutoReplyDecision(
        intent="itiraz",
        reply_text="Bütçe tarafını anlıyorum, 30 dakika görüşelim mi?",
        confidence=0.9,
        objection_type="fiyat",
    )


class TestNativeFlagOff:
    @pytest.mark.asyncio
    async def test_flag_off_keeps_legacy_handoff(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        monkeypatch.delenv("AUTO_REPLY_ITIRAZ_NATIVE", raising=False)

        async def fake_decide(message, **kwargs):
            return _itiraz_decision()

        monkeypatch.setattr(runner, "decide_reply", fake_decide)
        handoff = AsyncMock(return_value=True)
        monkeypatch.setattr(runner, "_handoff_to_n8n_itiraz", handoff)

        result = await runner.handle_one(
            inbound_row={
                "Id": 7,
                "mesaj_icerigi": "Fiyatınız yüksek",
                "lead_adi": "Otel A",
            },
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )

        assert result["reply_sent"] is False
        zernio.send_message.assert_not_called()
        assert handoff.await_args.kwargs["draft_reply"] == ""
        assert handoff.await_args.kwargs["objection_type"] is None
        log_row = next(
            c for c in nocodb.upsert_record.call_args_list
            if c.args[2].get("tur") == "Itiraz Handoff"
        )
        assert log_row is not None


class TestNativeFlagOn:
    @pytest.mark.asyncio
    async def test_flag_on_uses_draft_and_oneri_log(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        monkeypatch.setenv("AUTO_REPLY_ITIRAZ_NATIVE", "true")

        async def fake_decide(message, **kwargs):
            return _itiraz_decision()

        monkeypatch.setattr(runner, "decide_reply", fake_decide)
        handoff = AsyncMock(return_value=True)
        monkeypatch.setattr(runner, "_handoff_to_n8n_itiraz", handoff)

        result = await runner.handle_one(
            inbound_row={
                "Id": 7,
                "mesaj_icerigi": "Fiyatınız yüksek",
                "lead_adi": "Otel A",
            },
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )

        assert result["reply_sent"] is False
        zernio.send_message.assert_not_called()
        assert result["objection_type"] == "fiyat"

        kw = handoff.await_args.kwargs
        assert kw["draft_reply"].startswith("Bütçe")
        assert kw["objection_type"] == "fiyat"

        log_row = next(
            c for c in nocodb.upsert_record.call_args_list
            if c.args[2].get("tur") == "Itiraz Önerisi"
        )
        assert "ONERI taslagi" in log_row.args[2]["mesaj_icerigi"]
        assert "tip=fiyat" in log_row.args[2]["mesaj_icerigi"]

    @pytest.mark.asyncio
    async def test_flag_on_dry_run_writes_nothing(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        monkeypatch.setenv("AUTO_REPLY_ITIRAZ_NATIVE", "1")

        async def fake_decide(message, **kwargs):
            return _itiraz_decision()

        monkeypatch.setattr(runner, "decide_reply", fake_decide)
        handoff = AsyncMock(return_value=True)
        monkeypatch.setattr(runner, "_handoff_to_n8n_itiraz", handoff)

        await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "pahalı", "lead_adi": "A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=True,
        )
        handoff.assert_not_called()
        nocodb.upsert_record.assert_not_called()
