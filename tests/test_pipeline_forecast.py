"""Pipeline forecast — Firsatlar tablosu, weighted (Teklif 0.3 + Sozlesme 0.7 + Kazanildi 1.0)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


@pytest.fixture
def patch_fetch_all(monkeypatch):
    """Patch _fetch_all in management_tools to control Firsatlar rows."""
    from src.tools.sales import management_tools

    rows_holder: dict = {"rows": []}

    def fake_fetch_all(table_id, **kwargs):
        rows_holder["table"] = table_id
        return rows_holder["rows"]

    monkeypatch.setattr(management_tools, "_fetch_all", fake_fetch_all)
    return rows_holder


class TestPipelineForecast:
    @pytest.mark.asyncio
    async def test_weighted_calculation(self, patch_fetch_all):
        patch_fetch_all["rows"] = [
            {"asama": "Teklif", "tutar": 100000},
            {"asama": "Teklif", "tutar": 50000},
            {"asama": "Sozlesme", "tutar": 200000},
            {"asama": "Kazanildi", "tutar": 80000},
            {"asama": "Kayip", "tutar": 30000},
        ]
        from src.tools.sales.management_tools import _pipeline_forecast_impl
        result = await _pipeline_forecast_impl()
        assert result["success"] is True
        # total_open = Teklif + Sozlesme totals = 150000 + 200000 = 350000
        assert result["total_open"] == 350000.0
        assert result["total_won"] == 80000.0
        # weighted = 150000*0.3 + 200000*0.7 + 80000*1.0 = 45000 + 140000 + 80000 = 265000
        assert result["weighted_forecast"] == 265000.0

    @pytest.mark.asyncio
    async def test_uses_env_table_id(self, patch_fetch_all, monkeypatch):
        monkeypatch.setenv("NOCODB_FIRSATLAR_TABLE_ID", "custom_firsatlar")
        patch_fetch_all["rows"] = []
        from src.tools.sales.management_tools import _pipeline_forecast_impl
        await _pipeline_forecast_impl()
        assert patch_fetch_all["table"] == "custom_firsatlar"

    @pytest.mark.asyncio
    async def test_default_table_id_used_when_no_env(self, patch_fetch_all, monkeypatch):
        monkeypatch.delenv("NOCODB_FIRSATLAR_TABLE_ID", raising=False)
        patch_fetch_all["rows"] = []
        from src.tools.sales.management_tools import (
            _pipeline_forecast_impl,
            DEFAULT_FIRSATLAR_TABLE_ID,
        )
        await _pipeline_forecast_impl()
        assert patch_fetch_all["table"] == DEFAULT_FIRSATLAR_TABLE_ID

    @pytest.mark.asyncio
    async def test_empty_rows(self, patch_fetch_all):
        patch_fetch_all["rows"] = []
        from src.tools.sales.management_tools import _pipeline_forecast_impl
        result = await _pipeline_forecast_impl()
        assert result["success"] is True
        assert result["total_open"] == 0
        assert result["weighted_forecast"] == 0
        assert result["by_stage"] == []
