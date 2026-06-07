"""Faz 5 — mark_lead_qualified tool testleri.

Migration'ın eklediği qualifier alanlarını (qualified, qualification_reason,
qualified_by, qualified_at, source) Leadler satırına yazan tool. NocoDB client
mock'lu; network yok.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    client.update_record.return_value = {"Id": 42, "qualified": True}
    import src.tools.sales.nocodb_tools as nt
    monkeypatch.setattr(nt, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    from src.app import config as cfg
    cfg.get_settings.cache_clear()
    yield client
    cfg.get_settings.cache_clear()


class TestMarkLeadQualified:
    @pytest.mark.asyncio
    async def test_qualify_true_writes_all_fields(self, mock_nocodb):
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        result = await _mark_lead_qualified_impl(
            lead_id=42,
            qualified=True,
            qualification_reason="Bodrum otelcilik, ICP tam uyum",
            source="gmaps",
        )
        assert result["success"] is True
        table, lead_id, fields = mock_nocodb.update_record.call_args[0]
        assert table == "leads_tbl"
        assert lead_id == 42
        assert fields["qualified"] is True
        assert fields["qualification_reason"] == "Bodrum otelcilik, ICP tam uyum"
        assert fields["source"] == "gmaps"
        assert fields["qualified_by"] == "qualifier_agent"
        assert "qualified_at" in fields  # otomatik timestamp

    @pytest.mark.asyncio
    async def test_qualify_false_still_records_reason(self, mock_nocodb):
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        result = await _mark_lead_qualified_impl(
            lead_id=7,
            qualified=False,
            qualification_reason="ICP dışı sektör",
        )
        assert result["success"] is True
        _, _, fields = mock_nocodb.update_record.call_args[0]
        assert fields["qualified"] is False
        assert fields["qualification_reason"] == "ICP dışı sektör"

    @pytest.mark.asyncio
    async def test_optional_asama_passed_through(self, mock_nocodb):
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        await _mark_lead_qualified_impl(
            lead_id=42,
            qualified=True,
            qualification_reason="uygun",
            asama="Sicak",
        )
        _, _, fields = mock_nocodb.update_record.call_args[0]
        assert fields["asama"] == "Sicak"

    @pytest.mark.asyncio
    async def test_invalid_source_rejected(self, mock_nocodb):
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        result = await _mark_lead_qualified_impl(
            lead_id=42,
            qualified=True,
            qualification_reason="uygun",
            source="quora",  # geçersiz option
        )
        assert result["success"] is False
        mock_nocodb.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_reason_rejected(self, mock_nocodb):
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        result = await _mark_lead_qualified_impl(
            lead_id=42, qualified=True, qualification_reason="  "
        )
        assert result["success"] is False
        mock_nocodb.update_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_table_error(self, monkeypatch):
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
        from src.app import config as cfg
        cfg.get_settings.cache_clear()
        from src.tools.sales.nocodb_tools import _mark_lead_qualified_impl
        result = await _mark_lead_qualified_impl(
            lead_id=42, qualified=True, qualification_reason="uygun"
        )
        assert result["success"] is False
        cfg.get_settings.cache_clear()
