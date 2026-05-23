"""Sales Director lead write tools: assign_lead, update_lead_stage, add_lead_note."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    client.update_record.return_value = {"Id": 42, "ok": True}
    client.get_record.return_value = {"Id": 42, "notlar": ""}
    from src.tools.sales import management_tools, reporting_tools
    monkeypatch.setattr(management_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setattr(reporting_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    # invalidate get_settings cache so env override is read
    from src.app import config as cfg
    cfg.get_settings.cache_clear()
    yield client
    cfg.get_settings.cache_clear()


class TestAssignLead:
    @pytest.mark.asyncio
    async def test_success(self, mock_nocodb):
        from src.tools.sales.management_tools import _assign_lead_impl
        result = await _assign_lead_impl(lead_id=42, atanan_kisi="Seyma")
        assert result["success"] is True
        assert result["atanan_kisi"] == "Seyma"
        mock_nocodb.update_record.assert_called_once_with(
            "leads_tbl", 42, {"atanan_kisi": "Seyma"}
        )

    @pytest.mark.asyncio
    async def test_empty_assignee_rejected(self, mock_nocodb):
        from src.tools.sales.management_tools import _assign_lead_impl
        result = await _assign_lead_impl(lead_id=42, atanan_kisi="  ")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"
        mock_nocodb.update_record.assert_not_called()


class TestUpdateLeadStage:
    @pytest.mark.asyncio
    async def test_valid_stage(self, mock_nocodb):
        from src.tools.sales.management_tools import _update_lead_stage_impl
        result = await _update_lead_stage_impl(lead_id=42, asama="Sicak")
        assert result["success"] is True
        assert result["asama"] == "Sicak"
        # No reason -> no notlar update
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields == {"asama": "Sicak"}

    @pytest.mark.asyncio
    async def test_invalid_stage_rejected(self, mock_nocodb):
        from src.tools.sales.management_tools import _update_lead_stage_impl
        result = await _update_lead_stage_impl(lead_id=42, asama="NotAStage")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"
        mock_nocodb.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_reason_appended_to_notlar(self, mock_nocodb):
        mock_nocodb.get_record.return_value = {"Id": 42, "notlar": "eski not"}
        from src.tools.sales.management_tools import _update_lead_stage_impl
        result = await _update_lead_stage_impl(
            lead_id=42, asama="Kazanildi", reason="Sozlesme imzalandi"
        )
        assert result["success"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert fields["asama"] == "Kazanildi"
        assert "eski not" in fields["notlar"]
        assert "Sozlesme imzalandi" in fields["notlar"]

    @pytest.mark.asyncio
    async def test_takipte_and_itiraz_valid(self, mock_nocodb):
        from src.tools.sales.management_tools import _update_lead_stage_impl
        r1 = await _update_lead_stage_impl(lead_id=42, asama="Takipte")
        r2 = await _update_lead_stage_impl(lead_id=42, asama="Itiraz")
        assert r1["success"] and r2["success"]


class TestAddLeadNote:
    @pytest.mark.asyncio
    async def test_appends_to_existing_notes(self, mock_nocodb):
        mock_nocodb.get_record.return_value = {"Id": 42, "notlar": "onceki not"}
        from src.tools.sales.management_tools import _add_lead_note_impl
        result = await _add_lead_note_impl(lead_id=42, note="yeni not")
        assert result["success"] is True
        fields = mock_nocodb.update_record.call_args.args[2]
        assert "onceki not" in fields["notlar"]
        assert "yeni not" in fields["notlar"]

    @pytest.mark.asyncio
    async def test_empty_note_rejected(self, mock_nocodb):
        from src.tools.sales.management_tools import _add_lead_note_impl
        result = await _add_lead_note_impl(lead_id=42, note=" ")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


class TestRegistration:
    def test_management_tools_includes_lead_writes(self):
        from src.tools.sales.management_tools import get_management_tools
        names = {t.name for t in get_management_tools()}
        assert {"assign_lead", "update_lead_stage", "add_lead_note"} <= names
