"""Auto-reply konusma hafizasi: fetch_recent_history + responder prompt + runner integration."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.auto_reply.policy import AutoReplyConfig  # noqa: E402
from src.agents.auto_reply.responder import (  # noqa: E402
    AutoReplyDecision,
    _build_user_prompt,
    _format_history,
)
from src.agents.auto_reply.targeting import fetch_recent_history  # noqa: E402
from src.agents.auto_reply import runner  # noqa: E402


class TestFetchRecentHistory:
    def test_empty_name_returns_empty(self):
        client = MagicMock()
        assert fetch_recent_history(client, "msgs", "") == []
        client.list_records.assert_not_called()

    def test_orders_oldest_first(self):
        client = MagicMock()
        # NocoDB -tarih sort -> en yeni once dondurur; biz reverse ederiz
        client.list_records.return_value = {
            "list": [
                {"Id": 3, "tarih": "2026-05-18", "mesaj_icerigi": "yeni"},
                {"Id": 2, "tarih": "2026-05-17", "mesaj_icerigi": "orta"},
                {"Id": 1, "tarih": "2026-05-15", "mesaj_icerigi": "eski"},
            ]
        }
        rows = fetch_recent_history(client, "msgs", "Otel A", limit=3)
        assert [r["Id"] for r in rows] == [1, 2, 3]
        kwargs = client.list_records.call_args.kwargs
        assert kwargs["sort"] == "-tarih"
        assert "(lead_adi,eq,Otel A)" in kwargs["where"]

    def test_excludes_current_row(self):
        client = MagicMock()
        client.list_records.return_value = {
            "list": [
                {"Id": 7, "tarih": "2026-05-18", "mesaj_icerigi": "yeni"},
                {"Id": 5, "tarih": "2026-05-15", "mesaj_icerigi": "eski"},
            ]
        }
        rows = fetch_recent_history(client, "msgs", "Otel A", limit=10, exclude_row_id=7)
        assert [r["Id"] for r in rows] == [5]

    def test_nocodb_error_returns_empty(self):
        client = MagicMock()
        client.list_records.side_effect = RuntimeError("nocodb down")
        # Defansif — hata bos liste demek; hafiza opsiyonel
        assert fetch_recent_history(client, "msgs", "Otel A") == []

    def test_comma_in_name_is_sanitized(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        fetch_recent_history(client, "msgs", "Otel, A")
        where = client.list_records.call_args.kwargs["where"]
        # Virgul kacirilmali ki NocoDB filter ayraciyla karismasin
        assert "Otel  A" in where
        assert "Otel, A" not in where


class TestPromptWithHistory:
    def test_format_history_compact(self):
        h = [
            {"yon": "Giden", "tur": "Ilk Mesaj", "tarih": "2026-05-10T08:00:00Z", "mesaj_icerigi": "Template gonderildi"},
            {"yon": "Gelen", "tur": "-", "tarih": "2026-05-11T09:30:00Z", "mesaj_icerigi": "ilgileniyorum"},
        ]
        text = _format_history(h)
        assert text is not None
        assert "Giden" in text and "Gelen" in text
        assert "2026-05-10" in text
        assert "ilgileniyorum" in text

    def test_format_history_none_when_empty(self):
        assert _format_history(None) is None
        assert _format_history([]) is None

    def test_long_message_truncated(self):
        long_text = "x" * 500
        text = _format_history([{"yon": "Gelen", "tarih": "2026-05-11", "mesaj_icerigi": long_text}])
        assert text is not None
        assert len(text) < 500
        assert text.endswith("…")

    def test_build_user_prompt_includes_history(self):
        h = [{"yon": "Gelen", "tur": "-", "tarih": "2026-05-11", "mesaj_icerigi": "selam"}]
        p = _build_user_prompt("yeni mesaj", None, None, history=h)
        assert "ONCEKI KONUSMA" in p
        assert "selam" in p

    def test_build_user_prompt_omits_history_when_none(self):
        p = _build_user_prompt("yeni", None, None)
        assert "ONCEKI KONUSMA" not in p


@pytest.fixture
def mock_clients(monkeypatch):
    nocodb = MagicMock()
    nocodb.find_by_field.return_value = {"Id": 42, "telefon": "+905551112233"}
    nocodb.list_records.return_value = {"list": []}  # default empty history
    zernio = MagicMock()
    zernio.find_conversation_by_phone = AsyncMock(return_value={"id": "conv-1"})
    zernio.send_message = AsyncMock(return_value={"messageId": "wamid.OUT"})
    monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
    monkeypatch.setattr(runner, "get_zernio_client", lambda: zernio)
    return nocodb, zernio


class TestHandleOneWithHistory:
    @pytest.mark.asyncio
    async def test_history_fetched_and_passed_to_decide_reply(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        nocodb.list_records.return_value = {
            "list": [
                {"Id": 99, "tarih": "2026-05-18", "yon": "Giden", "mesaj_icerigi": "Tesekkurler"},
                {"Id": 90, "tarih": "2026-05-15", "yon": "Gelen", "mesaj_icerigi": "merhaba"},
            ]
        }
        captured = {}

        async def fake_decide(message, **kwargs):
            captured["history"] = kwargs.get("conversation_history")
            return AutoReplyDecision(intent="olumlu", reply_text="cevap", confidence=0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "evet", "lead_adi": "Otel A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        # History 2 satir geldi, kronolojik
        assert result["history_size"] == 2
        assert captured["history"] is not None
        assert [r["Id"] for r in captured["history"]] == [90, 99]

    @pytest.mark.asyncio
    async def test_history_error_falls_back_to_empty(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        # Once list_records cagrildiginda hata, sonra normal cagrilar
        call_count = {"n": 0}
        original_list = nocodb.list_records

        def flaky_list(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("nocodb down")
            return {"list": []}

        nocodb.list_records = flaky_list
        captured = {}

        async def fake_decide(message, **kwargs):
            captured["history"] = kwargs.get("conversation_history")
            return AutoReplyDecision(intent="olumlu", reply_text="cevap", confidence=0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "evet", "lead_adi": "Otel A"},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        # Hata yutuldu, bos history ile devam
        assert result["history_size"] == 0
        assert captured["history"] == []
        # Mesaj yine de gonderildi
        assert result["reply_sent"] is True

    @pytest.mark.asyncio
    async def test_no_lead_name_no_history_fetch(self, mock_clients, monkeypatch):
        nocodb, zernio = mock_clients
        captured = {}

        async def fake_decide(message, **kwargs):
            captured["history"] = kwargs.get("conversation_history")
            return AutoReplyDecision(intent="olumlu", reply_text="cevap", confidence=0.9)

        monkeypatch.setattr(runner, "decide_reply", fake_decide)

        result = await runner.handle_one(
            inbound_row={"Id": 7, "mesaj_icerigi": "evet", "lead_adi": ""},
            config=AutoReplyConfig(),
            leads_table="leads_tbl",
            messages_table="msgs_tbl",
            dry_run=False,
        )
        # lead_adi bos -> history fetch hic denenmedi
        assert result["history_size"] == 0
        # list_records cagrilmadi (history fetch icin)
        nocodb.list_records.assert_not_called()
