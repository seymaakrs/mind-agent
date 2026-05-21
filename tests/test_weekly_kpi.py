"""Weekly KPI tool — sicak + kazanildi hedef vs gercek (Pazartesi UTC -> bugun)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def mock_nocodb(monkeypatch):
    client = MagicMock()
    from src.tools.sales import management_tools, reporting_tools
    monkeypatch.setattr(management_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setattr(reporting_tools, "get_nocodb_client", lambda: client)
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    from src.app import config as cfg
    cfg.get_settings.cache_clear()
    yield client
    cfg.get_settings.cache_clear()


class TestWeeklyKpi:
    @pytest.mark.asyncio
    async def test_pct_calculation(self, mock_nocodb):
        # count_records called twice (sicak, kazanildi)
        mock_nocodb.count_records.side_effect = [18, 2]
        from src.tools.sales.management_tools import _weekly_kpi_impl
        result = await _weekly_kpi_impl(target_sicak=30, target_kazanildi=5)
        assert result["success"] is True
        assert result["actual_sicak"] == 18
        assert result["actual_kazanildi"] == 2
        assert result["target_sicak"] == 30
        assert result["sicak_pct"] == 60.0
        assert result["kazanildi_pct"] == 40.0

    @pytest.mark.asyncio
    async def test_zero_target_safe(self, mock_nocodb):
        mock_nocodb.count_records.side_effect = [5, 0]
        from src.tools.sales.management_tools import _weekly_kpi_impl
        result = await _weekly_kpi_impl(target_sicak=0, target_kazanildi=0)
        assert result["success"] is True
        assert result["sicak_pct"] == 0.0
        assert result["kazanildi_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_week_start_in_filters(self, mock_nocodb):
        mock_nocodb.count_records.side_effect = [0, 0]
        from src.tools.sales.management_tools import _weekly_kpi_impl
        result = await _weekly_kpi_impl(target_sicak=1, target_kazanildi=1)
        # week_start should be a Monday (weekday 0)
        d = datetime.fromisoformat(result["week_start"])
        assert d.weekday() == 0
        # NocoDB call should include exactDate for week_start
        where_calls = [c.kwargs.get("where") for c in mock_nocodb.count_records.call_args_list]
        assert any(result["week_start"] in (w or "") for w in where_calls)


class TestWeekStartHelper:
    def test_monday_already(self):
        from src.tools.sales.management_tools import _week_start_utc
        monday = datetime(2026, 5, 18, 14, 30, tzinfo=timezone.utc)  # 2026-05-18 Mon
        assert monday.weekday() == 0
        start = _week_start_utc(monday)
        assert start.weekday() == 0
        assert start.hour == 0 and start.minute == 0

    def test_wednesday_rolls_back_to_monday(self):
        from src.tools.sales.management_tools import _week_start_utc
        wed = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
        assert wed.weekday() == 2
        start = _week_start_utc(wed)
        assert start.weekday() == 0
        assert start.date().isoformat() == "2026-05-18"
