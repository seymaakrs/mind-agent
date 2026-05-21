"""Sales Director Faz 2 birim tool tests (Avcilik / CX / Kalite)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    client.update_record.return_value = {"Id": 1, "ok": True}
    client.get_record.return_value = {"Id": 42, "notlar": ""}
    client.list_records.return_value = {"list": []}
    from src.tools.sales import management_tools, reporting_tools
    monkeypatch.setattr(management_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setattr(reporting_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "settings_tbl")
    monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
    from src.app import config as cfg
    cfg.get_settings.cache_clear()
    yield client
    cfg.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Avcilik Birimi
# ---------------------------------------------------------------------------


class TestOutreachSetDailyLimit:
    @pytest.mark.asyncio
    async def test_valid(self, mock_nocodb):
        from src.tools.sales.management_tools import _outreach_set_daily_limit_impl
        r = await _outreach_set_daily_limit_impl(120)
        assert r["success"] is True
        assert r["new_limit"] == 120
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["outreach_daily_limit"] == 120
        assert "outreach_limit_updated_at" in fields

    @pytest.mark.asyncio
    async def test_negative_rejected(self, mock_nocodb):
        from src.tools.sales.management_tools import _outreach_set_daily_limit_impl
        r = await _outreach_set_daily_limit_impl(-1)
        assert r["success"] is False
        assert r["error_code"] == "INVALID_INPUT"
        mock_nocodb.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_above_max_rejected(self, mock_nocodb):
        from src.tools.sales.management_tools import _outreach_set_daily_limit_impl
        r = await _outreach_set_daily_limit_impl(501)
        assert r["success"] is False
        assert r["error_code"] == "INVALID_INPUT"


class TestOutreachTargetPreview:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_nocodb):
        mock_nocodb.list_records.return_value = {
            "list": [
                {"Id": 1, "ad_soyad": "A", "telefon": "+90555", "sirket_adi": "X"},
                {"Id": 2, "ad_soyad": "B", "telefon": "+90556", "sirket_adi": "Y"},
            ]
        }
        from src.tools.sales.management_tools import _outreach_target_preview_impl
        r = await _outreach_target_preview_impl(limit=5)
        assert r["success"] is True
        assert r["count"] == 2
        assert r["data"][0]["Id"] == 1

    @pytest.mark.asyncio
    async def test_limit_capped(self, mock_nocodb):
        from src.tools.sales.management_tools import _outreach_target_preview_impl
        await _outreach_target_preview_impl(limit=200)
        kwargs = mock_nocodb.list_records.call_args.kwargs
        assert kwargs["limit"] == 50


class TestOutreachSkipLead:
    @pytest.mark.asyncio
    async def test_requires_reason(self, mock_nocodb):
        from src.tools.sales.management_tools import _outreach_skip_lead_impl
        r = await _outreach_skip_lead_impl(lead_id=42, reason="  ")
        assert r["success"] is False
        assert r["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_appends_note_and_archives(self, mock_nocodb):
        mock_nocodb.get_record.return_value = {"Id": 42, "notlar": "eski"}
        from src.tools.sales.management_tools import _outreach_skip_lead_impl
        r = await _outreach_skip_lead_impl(lead_id=42, reason="rakip")
        assert r["success"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["asama"] == "Arsiv"
        assert "[SKIP]" in fields["notlar"]
        assert "rakip" in fields["notlar"]
        assert "eski" in fields["notlar"]


# ---------------------------------------------------------------------------
# CX Birimi
# ---------------------------------------------------------------------------


class TestAutoReplyTemplateList:
    @pytest.mark.asyncio
    async def test_not_configured(self, mock_nocodb, monkeypatch):
        monkeypatch.delenv("NOCODB_TEMPLATES_TABLE_ID", raising=False)
        from src.tools.sales.management_tools import _auto_reply_template_list_impl
        r = await _auto_reply_template_list_impl()
        assert r["success"] is False
        assert r["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_configured(self, mock_nocodb, monkeypatch):
        monkeypatch.setenv("NOCODB_TEMPLATES_TABLE_ID", "tmpl_tbl")
        mock_nocodb.list_records.return_value = {
            "list": [{"Id": 1, "ad": "selam", "icerik": "Merhaba!", "aktif": True}]
        }
        from src.tools.sales.management_tools import _auto_reply_template_list_impl
        r = await _auto_reply_template_list_impl()
        assert r["success"] is True
        assert r["count"] == 1


class TestAutoReplyTemplateUpdate:
    @pytest.mark.asyncio
    async def test_empty_rejected(self, mock_nocodb, monkeypatch):
        monkeypatch.setenv("NOCODB_TEMPLATES_TABLE_ID", "tmpl_tbl")
        from src.tools.sales.management_tools import _auto_reply_template_update_impl
        r = await _auto_reply_template_update_impl(template_id=1, icerik="")
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_valid(self, mock_nocodb, monkeypatch):
        monkeypatch.setenv("NOCODB_TEMPLATES_TABLE_ID", "tmpl_tbl")
        from src.tools.sales.management_tools import _auto_reply_template_update_impl
        r = await _auto_reply_template_update_impl(template_id=5, icerik="Yeni metin")
        assert r["success"] is True
        mock_nocodb.update_record.assert_called_once()


class TestAutoReplySetDailyCap:
    @pytest.mark.asyncio
    async def test_valid(self, mock_nocodb):
        from src.tools.sales.management_tools import _auto_reply_set_daily_cap_impl
        r = await _auto_reply_set_daily_cap_impl(50)
        assert r["success"] is True
        assert r["new_cap"] == 50

    @pytest.mark.asyncio
    async def test_invalid(self, mock_nocodb):
        from src.tools.sales.management_tools import _auto_reply_set_daily_cap_impl
        r = await _auto_reply_set_daily_cap_impl(1001)
        assert r["success"] is False


class TestFlagForHuman:
    @pytest.mark.asyncio
    async def test_requires_reason(self, mock_nocodb):
        from src.tools.sales.management_tools import _flag_for_human_impl
        r = await _flag_for_human_impl(lead_id=42, reason="")
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_writes_stage_and_note(self, mock_nocodb):
        mock_nocodb.get_record.return_value = {"Id": 42, "notlar": ""}
        from src.tools.sales.management_tools import _flag_for_human_impl
        r = await _flag_for_human_impl(lead_id=42, reason="hassas itiraz")
        assert r["success"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["asama"] in ("Manuel Inceleme", "Itiraz")
        assert "FLAG" in fields["notlar"] or "MANUEL" in fields["notlar"]
        assert "son_temas" in fields


# ---------------------------------------------------------------------------
# Kalite Birimi
# ---------------------------------------------------------------------------


class TestGuardianSetThresholds:
    @pytest.mark.asyncio
    async def test_red_must_be_less_than_yellow(self, mock_nocodb):
        from src.tools.sales.management_tools import _guardian_set_thresholds_impl
        r = await _guardian_set_thresholds_impl(
            reply_rate_yellow=3.0, reply_rate_red=5.0
        )
        assert r["success"] is False
        assert r["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_valid_write(self, mock_nocodb):
        from src.tools.sales.management_tools import _guardian_set_thresholds_impl
        r = await _guardian_set_thresholds_impl(
            reply_rate_yellow=5.0, reply_rate_red=2.0
        )
        assert r["success"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["guardian_reply_yellow_pct"] == 5.0
        assert fields["guardian_reply_red_pct"] == 2.0

    @pytest.mark.asyncio
    async def test_out_of_range(self, mock_nocodb):
        from src.tools.sales.management_tools import _guardian_set_thresholds_impl
        r = await _guardian_set_thresholds_impl(
            reply_rate_yellow=150.0, reply_rate_red=10.0
        )
        assert r["success"] is False


class TestComplianceAudit:
    @pytest.mark.asyncio
    async def test_returns_shape(self, mock_nocodb):
        # _fetch_all paginates list_records — simulate empty pages
        mock_nocodb.list_records.return_value = {
            "list": [], "pageInfo": {"isLastPage": True}
        }
        from src.tools.sales.management_tools import _compliance_audit_impl
        r = await _compliance_audit_impl(days=7)
        assert r["success"] is True
        assert r["window_days"] == 7
        assert "total_inbound" in r
        assert "total_outbound" in r
        assert "failed_sends" in r
        assert "summary_tr" in r


# ---------------------------------------------------------------------------
# Factory wiring
# ---------------------------------------------------------------------------


class TestUnitFactories:
    def test_outreach_unit_has_5(self):
        from src.tools.sales.management_tools import get_outreach_unit_tools
        tools = get_outreach_unit_tools()
        names = {t.name for t in tools}
        assert names == {
            "outreach_pause", "outreach_resume", "outreach_set_daily_limit",
            "outreach_target_preview", "outreach_skip_lead",
        }

    def test_cx_unit_has_6(self):
        from src.tools.sales.management_tools import get_cx_unit_tools
        tools = get_cx_unit_tools()
        names = {t.name for t in tools}
        assert names == {
            "auto_reply_pause", "auto_reply_resume",
            "auto_reply_template_list", "auto_reply_template_update",
            "auto_reply_set_daily_cap", "flag_for_human",
        }

    def test_quality_unit_has_2(self):
        from src.tools.sales.management_tools import get_quality_unit_tools
        tools = get_quality_unit_tools()
        names = {t.name for t in tools}
        assert names == {"guardian_set_thresholds", "compliance_audit"}

    def test_director_total_tool_count(self):
        from src.agents.sales.sales_manager_agent import create_sales_manager_agent
        agent = create_sales_manager_agent()
        # 10 read + 5 + 6 + 2 + 7 = 30
        assert len(agent.tools) == 30
