"""Sales Manager yazma aksiyonları (TODO A) testleri.

Bütün impl'ler async. Her aksiyon NocoDB'ye `update_record` / `create_record`
çağırır + best-effort audit log.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import src.tools.sales.manager_actions as ma


@pytest.fixture
def fake_client(monkeypatch):
    client = MagicMock()
    client.list_records.return_value = {
        "list": [{"Id": 1, "outreach_daily_limit": 240}]
    }
    client.update_record.return_value = {"Id": 1, "ok": True}
    client.create_record.return_value = {"Id": 99}
    client.find_by_field.return_value = {"Id": 7, "intent": "olumlu"}
    monkeypatch.setattr(ma, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    monkeypatch.setenv("NOCODB_TEMPLATES_TABLE_ID", "tpl_tbl")
    monkeypatch.delenv("NOCODB_MANAGER_ACTIONS_TABLE_ID", raising=False)
    return client


class TestOutreachPause:
    @pytest.mark.asyncio
    async def test_pause_success(self, fake_client):
        result = await ma._outreach_pause_impl(reason="reply rate %2.1 esik alti")
        assert result["success"] is True
        assert result["action"] == "paused"
        fake_client.update_record.assert_called_once()
        args, kwargs = fake_client.update_record.call_args
        assert args[0] == "settings_tbl"
        assert args[1] == 1
        assert args[2]["outreach_paused"] is True
        assert "paused_at" in args[2]

    @pytest.mark.asyncio
    async def test_pause_rejects_short_reason(self, fake_client):
        result = await ma._outreach_pause_impl(reason="ok")
        assert result["success"] is False
        assert "5 karakter" in result["error"]
        fake_client.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_no_settings_table(self, monkeypatch):
        monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
        result = await ma._outreach_pause_impl(reason="some valid reason here")
        assert result["success"] is False


class TestOutreachResume:
    @pytest.mark.asyncio
    async def test_resume_success(self, fake_client):
        result = await ma._outreach_resume_impl(reason="bekci yesile dondu")
        assert result["success"] is True
        assert result["action"] == "resumed"
        args = fake_client.update_record.call_args.args
        assert args[2]["outreach_paused"] is False
        assert args[2]["pause_reason"] is None


class TestLeadReassign:
    @pytest.mark.asyncio
    async def test_reassign_updates_owner(self, fake_client):
        result = await ma._lead_reassign_impl(
            lead_id=42, new_owner="Beyza", reason="Seyma musait degil"
        )
        assert result["success"] is True
        assert result["new_owner"] == "Beyza"
        args = fake_client.update_record.call_args.args
        assert args[0] == "leads_tbl"
        assert args[1] == 42
        assert args[2]["atanan_kisi"] == "Beyza"

    @pytest.mark.asyncio
    async def test_reassign_requires_owner(self, fake_client):
        result = await ma._lead_reassign_impl(
            lead_id=1, new_owner="", reason="valid reason here"
        )
        assert result["success"] is False


class TestLeadPriority:
    @pytest.mark.asyncio
    async def test_set_acil_priority(self, fake_client):
        result = await ma._lead_priority_set_impl(
            lead_id=5, priority="acil", reason="teklif istedi"
        )
        assert result["success"] is True
        assert result["priority"] == "acil"
        args = fake_client.update_record.call_args.args
        assert args[2]["priority"] == "acil"

    @pytest.mark.asyncio
    async def test_invalid_priority_rejected(self, fake_client):
        result = await ma._lead_priority_set_impl(
            lead_id=5, priority="kritik", reason="hata test"
        )
        assert result["success"] is False
        assert "priority" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_priority_case_insensitive(self, fake_client):
        result = await ma._lead_priority_set_impl(
            lead_id=5, priority="ACIL", reason="case test gecti"
        )
        assert result["success"] is True
        assert result["priority"] == "acil"


class TestAutoReplyTemplate:
    @pytest.mark.asyncio
    async def test_template_update_existing_intent(self, fake_client):
        result = await ma._auto_reply_template_update_impl(
            intent="olumlu",
            new_text="Merhaba! Slowdays olarak size yardimci olmak isteriz.",
            reason="reply rate iyilestirme",
        )
        assert result["success"] is True
        assert result["operation"] == "updated"
        fake_client.update_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_template_create_when_missing(self, fake_client):
        fake_client.find_by_field.return_value = None
        result = await ma._auto_reply_template_update_impl(
            intent="itiraz",
            new_text="Anlayisla yaklasiyoruz, bilgi alma istegimizi ileterim.",
            reason="yeni intent eklendi",
        )
        assert result["success"] is True
        assert result["operation"] == "created"
        fake_client.create_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_short_text_rejected(self, fake_client):
        result = await ma._auto_reply_template_update_impl(
            intent="olumlu",
            new_text="kisa",
            reason="bu calismayacak",
        )
        assert result["success"] is False


class TestDailyLimit:
    @pytest.mark.asyncio
    async def test_lower_limit(self, fake_client):
        result = await ma._outreach_daily_limit_set_impl(
            new_limit=120, reason="bekci YELLOW, riski azalt"
        )
        assert result["success"] is True
        assert result["new_limit"] == 120
        args = fake_client.update_record.call_args.args
        assert args[2]["outreach_daily_limit"] == 120

    @pytest.mark.asyncio
    async def test_zero_allowed(self, fake_client):
        result = await ma._outreach_daily_limit_set_impl(
            new_limit=0, reason="acil tam durus"
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_negative_rejected(self, fake_client):
        result = await ma._outreach_daily_limit_set_impl(
            new_limit=-5, reason="hatali deger denemesi"
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_over_max_rejected(self, fake_client):
        result = await ma._outreach_daily_limit_set_impl(
            new_limit=5000, reason="cok yuksek hata"
        )
        assert result["success"] is False


class TestRegistry:
    def test_all_six_tools_registered(self):
        tools = ma.get_manager_action_tools()
        names = {t.name for t in tools}
        assert names == {
            "outreach_pause",
            "outreach_resume",
            "lead_reassign",
            "lead_priority_set",
            "auto_reply_template_update",
            "outreach_daily_limit_set",
        }

    def test_sales_manager_includes_action_tools(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent
        agent = create_sales_manager_agent()
        names = {t.name for t in agent.tools}
        # Eski wiring test'i 'olmamali' diyordu; artik OLMASI gerekir
        assert "outreach_pause" in names
        assert "outreach_resume" in names
        assert "lead_reassign" in names
        assert "lead_priority_set" in names
        assert "auto_reply_template_update" in names
        assert "outreach_daily_limit_set" in names
