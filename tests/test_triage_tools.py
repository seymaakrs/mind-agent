"""Tests for triage_tools."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.tools.sales import triage_tools
from src.tools.sales.triage_tools import (
    _triage_report_impl,
    _triage_stale_hot_leads_impl,
    get_triage_tools,
)


def _patch_stale(monkeypatch, leads):
    monkeypatch.setattr(
        "src.tools.sales.triage_tools._stale_leads_impl",
        AsyncMock(return_value={"success": True, "data": leads}),
    )


def _patch_writes(monkeypatch):
    priority_mock = AsyncMock(return_value={"success": True})
    reassign_mock = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(
        "src.tools.sales.triage_tools._lead_priority_set_impl",
        priority_mock,
    )
    monkeypatch.setattr(
        "src.tools.sales.triage_tools._lead_reassign_impl",
        reassign_mock,
    )
    return priority_mock, reassign_mock


_DEFAULT_LEADS = [
    {"Id": 1, "ad_soyad": "Ali", "atanan_kisi": "Seyma"},
    {"Id": 2, "ad_soyad": "Veli", "atanan_kisi": "Seyma"},
    {"Id": 3, "ad_soyad": "Ayse", "atanan_kisi": "Beyza"},
]


@pytest.mark.asyncio
async def test_triage_full_run(monkeypatch):
    _patch_stale(monkeypatch, list(_DEFAULT_LEADS))
    priority_mock, reassign_mock = _patch_writes(monkeypatch)

    res = await _triage_stale_hot_leads_impl(business_id="biz1")

    assert res["success"] is True
    data = res["data"]
    assert data["found_count"] == 3
    assert data["actioned_count"] == 2
    assert data["reassigned_count"] == 2
    assert data["skipped_count"] == 1
    assert data["dry_run"] is False
    assert priority_mock.await_count == 2
    assert reassign_mock.await_count == 2
    assert "summary_tr" in res


@pytest.mark.asyncio
async def test_triage_dry_run_no_writes(monkeypatch):
    _patch_stale(monkeypatch, list(_DEFAULT_LEADS))
    priority_mock, reassign_mock = _patch_writes(monkeypatch)

    res = await _triage_stale_hot_leads_impl(
        business_id="biz1", dry_run=True
    )

    assert res["success"] is True
    assert res["data"]["dry_run"] is True
    assert res["data"]["found_count"] == 3
    assert res["data"]["actioned_count"] == 0
    assert res["data"]["reassigned_count"] == 0
    assert priority_mock.await_count == 0
    assert reassign_mock.await_count == 0


@pytest.mark.asyncio
async def test_triage_empty_stale(monkeypatch):
    _patch_stale(monkeypatch, [])
    priority_mock, reassign_mock = _patch_writes(monkeypatch)

    res = await _triage_stale_hot_leads_impl(business_id="biz1")

    assert res["success"] is True
    assert res["data"]["found_count"] == 0
    assert res["data"]["actioned_count"] == 0
    assert priority_mock.await_count == 0
    assert reassign_mock.await_count == 0


@pytest.mark.asyncio
async def test_triage_invalid_days_zero(monkeypatch):
    _patch_stale(monkeypatch, [])
    _patch_writes(monkeypatch)
    res = await _triage_stale_hot_leads_impl(
        business_id="biz1", days_threshold=0
    )
    assert res["success"] is False
    assert "days_threshold" in res["error"]


@pytest.mark.asyncio
async def test_triage_invalid_days_too_large(monkeypatch):
    _patch_stale(monkeypatch, [])
    _patch_writes(monkeypatch)
    res = await _triage_stale_hot_leads_impl(
        business_id="biz1", days_threshold=100
    )
    assert res["success"] is False
    assert "days_threshold" in res["error"]


@pytest.mark.asyncio
async def test_triage_report_read_only(monkeypatch):
    _patch_stale(monkeypatch, list(_DEFAULT_LEADS))
    priority_mock, reassign_mock = _patch_writes(monkeypatch)

    res = await _triage_report_impl(business_id="biz1")

    assert res["success"] is True
    assert res["data"]["found_count"] == 3
    assert res["data"]["actioned_count"] == 0
    assert res["data"]["reassigned_count"] == 0
    assert res["data"]["dry_run"] is True
    assert priority_mock.await_count == 0
    assert reassign_mock.await_count == 0
    assert len(res["data"]["actions"]) == 3


def test_registry_has_two_tools():
    tools = get_triage_tools()
    assert len(tools) == 2
    # ensure module exports both impl
    assert triage_tools.triage_stale_hot_leads in tools
    assert triage_tools.triage_report in tools


@pytest.mark.asyncio
async def test_triage_invalid_business_id(monkeypatch):
    _patch_stale(monkeypatch, [])
    _patch_writes(monkeypatch)
    res = await _triage_stale_hot_leads_impl(business_id="")
    assert res["success"] is False
    assert "business_id" in res["error"]
