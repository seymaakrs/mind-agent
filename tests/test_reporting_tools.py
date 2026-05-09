"""Unit tests for src.tools.sales.reporting_tools.

NocoDB client and table-id resolvers are monkey-patched, so no real HTTP
or env config is required. Tests exercise filter construction, aggregation,
and limit handling — the contract layer that drives the Sales Analyst agent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.tools.sales import reporting_tools as rt


# ---------------------------------------------------------------------------
# Helpers — call the wrapped function_tool's inner coroutine directly
# ---------------------------------------------------------------------------


def _inner(tool: Any):
    """function_tool wraps the original coroutine — reach the underlying fn."""
    for attr in ("on_invoke_tool", "func", "_func", "fn"):
        cand = getattr(tool, attr, None)
        if callable(cand):
            return cand
    # Last resort: assume tool itself is callable
    return tool


def _make_client(rows: list[dict[str, Any]] | None = None) -> MagicMock:
    client = MagicMock()
    client.list_records.return_value = {
        "list": rows or [],
        "pageInfo": {"isLastPage": True, "totalRows": len(rows or [])},
    }
    return client


@pytest.fixture(autouse=True)
def _patch_table_ids(monkeypatch):
    monkeypatch.setattr(rt, "_leads_table", lambda: "leads_tbl")
    monkeypatch.setattr(rt, "_messages_table", lambda: "msgs_tbl")
    yield


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_clamp_limit_defaults_and_bounds():
    assert rt._clamp_limit(None) == rt.DEFAULT_LIMIT
    assert rt._clamp_limit(0) == rt.DEFAULT_LIMIT
    assert rt._clamp_limit(-5) == rt.DEFAULT_LIMIT
    assert rt._clamp_limit(7) == 7
    assert rt._clamp_limit(rt.MAX_LIMIT + 100) == rt.MAX_LIMIT


def test_build_where_all_none():
    assert rt._build_where() is None


def test_build_where_combines_with_and():
    where = rt._build_where(asama="Sicak", kaynak="Meta Ads")
    assert "(asama,eq,Sicak)" in where
    assert "(kaynak,eq,Meta Ads)" in where
    assert "~and" in where


def test_build_where_dates_use_default_field():
    where = rt._build_where(date_from="2026-05-01", date_to="2026-05-09")
    assert "(CreatedAt,ge,2026-05-01)" in where
    assert "(CreatedAt,le,2026-05-09)" in where


# ---------------------------------------------------------------------------
# count_leads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_leads_passes_filter_and_returns_total(monkeypatch):
    rows = [{"Id": i} for i in range(7)]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.count_leads)(asama="Sicak", kaynak="Meta Ads")

    assert result["success"] is True
    assert result["count"] == 7
    args, kwargs = client.list_records.call_args
    assert args[0] == "leads_tbl"
    assert "(asama,eq,Sicak)" in kwargs["where"]
    assert "(kaynak,eq,Meta Ads)" in kwargs["where"]


@pytest.mark.asyncio
async def test_count_leads_no_filters(monkeypatch):
    client = _make_client([{"Id": 1}, {"Id": 2}])
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.count_leads)()

    assert result["success"] is True
    assert result["count"] == 2
    _, kwargs = client.list_records.call_args
    assert kwargs.get("where") is None


# ---------------------------------------------------------------------------
# list_leads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_leads_clamps_limit_and_slims_payload(monkeypatch):
    rows = [
        {
            "Id": 1,
            "ad_soyad": "Ali",
            "sirket_adi": "Acme",
            "kaynak": "Clay",
            "asama": "Ilik",
            "lead_skoru": 72,
            "atanan_kisi": "Burak",
            "telefon": "+90...",
            "email": "ali@acme.com",
            "konum": "Bodrum",
            "CreatedAt": "2026-05-01T10:00:00Z",
            "secret_internal": "should be dropped",
        }
    ]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.list_leads)(asama="Ilik", limit=99999)

    assert result["success"] is True
    assert result["count"] == 1
    item = result["data"][0]
    assert item["ad_soyad"] == "Ali"
    assert "secret_internal" not in item
    _, kwargs = client.list_records.call_args
    assert kwargs["limit"] == rt.MAX_LIMIT
    assert "(asama,eq,Ilik)" in kwargs["where"]


# ---------------------------------------------------------------------------
# lead_funnel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lead_funnel_orders_canonical_stages(monkeypatch):
    rows = [
        {"asama": "Sicak"},
        {"asama": "Sicak"},
        {"asama": "Yeni"},
        {"asama": "Kazanildi"},
        {"asama": "ExoticStage"},
    ]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.lead_funnel)()

    assert result["success"] is True
    by_stage = {row["asama"]: row["count"] for row in result["data"]}
    assert by_stage["Sicak"] == 2
    assert by_stage["Yeni"] == 1
    assert by_stage["Kazanildi"] == 1
    assert by_stage["ExoticStage"] == 1
    # Canonical first
    canonical_indices = [
        i for i, r in enumerate(result["data"]) if r["asama"] in rt.FUNNEL_STAGES
    ]
    assert canonical_indices == sorted(canonical_indices)
    assert result["total"] == 5


# ---------------------------------------------------------------------------
# channel_breakdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_channel_breakdown_aggregates_count_and_avg(monkeypatch):
    rows = [
        {"kaynak": "Meta Ads", "lead_skoru": 80},
        {"kaynak": "Meta Ads", "lead_skoru": 60},
        {"kaynak": "Clay", "lead_skoru": 50},
        {"kaynak": None, "lead_skoru": None},
    ]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.channel_breakdown)()

    assert result["success"] is True
    by_ch = {row["kaynak"]: row for row in result["data"]}
    assert by_ch["Meta Ads"]["count"] == 2
    assert by_ch["Meta Ads"]["avg_skor"] == 70.0
    assert by_ch["Clay"]["count"] == 1
    assert by_ch["Bilinmeyen"]["count"] == 1
    # Sorted by count desc -> Meta Ads first
    assert result["data"][0]["kaynak"] == "Meta Ads"


# ---------------------------------------------------------------------------
# stale_leads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_leads_filters_by_age(monkeypatch):
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=5)).isoformat()
    rows = [
        {"Id": 1, "ad_soyad": "Fresh", "asama": "Sicak", "UpdatedAt": fresh},
        {"Id": 2, "ad_soyad": "Old", "asama": "Sicak", "UpdatedAt": old},
        {"Id": 3, "ad_soyad": "NoTs", "asama": "Sicak"},
    ]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.stale_leads)(asama="Sicak", days=3)

    assert result["success"] is True
    assert result["count"] == 1
    assert result["data"][0]["ad_soyad"] == "Old"
    assert result["data"][0]["gun"] >= 3


# ---------------------------------------------------------------------------
# lead_timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lead_timeline_uses_lead_adi_filter(monkeypatch):
    rows = [
        {
            "tarih": "2026-05-08T09:00:00Z",
            "kanal": "WhatsApp",
            "yon": "Giden",
            "tur": "Ilk Mesaj",
            "mesaj_icerigi": "Merhaba",
            "sonuc": "Yanit Bekleniyor",
            "agent": "Meta Agent",
        }
    ]
    client = _make_client(rows)
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.lead_timeline)(ad_soyad="Ali Demir", limit=5)

    assert result["success"] is True
    assert result["lead"] == "Ali Demir"
    assert result["count"] == 1
    _, kwargs = client.list_records.call_args
    assert kwargs["where"] == "(lead_adi,eq,Ali Demir)"
    assert kwargs["sort"] == "-tarih"
    assert kwargs["limit"] == 5


# ---------------------------------------------------------------------------
# daily_digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_digest_returns_metrics(monkeypatch):
    new_today = [
        {"kaynak": "Meta Ads"},
        {"kaynak": "Meta Ads"},
        {"kaynak": "Clay"},
    ]
    sicak_total = 5
    won_today: list[dict[str, Any]] = []
    seyma_waiting = [{"Id": 1}, {"Id": 2}]

    def list_records(table_id, *, where=None, limit=25, sort=None):
        if where and where.startswith("(asama,eq,Sicak)") and limit == 1:
            return {
                "list": [{"Id": 99}],
                "pageInfo": {"isLastPage": True, "totalRows": sicak_total},
            }
        if where and "(asama,eq,Kazanildi)" in where:
            return {"list": won_today, "pageInfo": {"isLastPage": True}}
        if where and "(atanan_kisi,eq,Seyma)" in where:
            return {"list": seyma_waiting, "pageInfo": {"isLastPage": True}}
        if where and where.startswith("(asama,eq,Sicak)"):
            return {
                "list": [{"Id": i} for i in range(sicak_total)],
                "pageInfo": {"isLastPage": True},
            }
        # default: new-today window
        return {"list": new_today, "pageInfo": {"isLastPage": True}}

    client = MagicMock()
    client.list_records.side_effect = list_records
    monkeypatch.setattr(rt, "get_nocodb_client", lambda: client)

    result = await _inner(rt.daily_digest)(date="2026-05-09")

    assert result["success"] is True
    data = result["data"]
    assert data["yeni_lead_count"] == 3
    assert data["sicak_count"] == sicak_total
    assert data["kazanildi_count"] == 0
    assert data["seyma_bekleyen_count"] == 2
    assert data["top_channel"] == "Meta Ads"


# ---------------------------------------------------------------------------
# Tool group
# ---------------------------------------------------------------------------


def test_get_reporting_tools_lists_all_seven():
    tools = rt.get_reporting_tools()
    assert len(tools) == 7
