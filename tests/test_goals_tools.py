"""Sales Manager aylik hedef + KPI takibi (goals_tools) testleri."""
from __future__ import annotations

import calendar
from datetime import date
from unittest.mock import MagicMock

import pytest

import src.tools.sales.goals_tools as gt


@pytest.fixture
def fake_doc_client(monkeypatch):
    """Mock Firestore document client + _count_leads_impl."""
    client = MagicMock()
    client.set_document.return_value = {"documentId": "x"}
    client.get_document.return_value = None
    client.list_documents.return_value = []
    monkeypatch.setattr(gt, "get_document_client", lambda _path: client)

    async def fake_count(**_kwargs):
        return {"success": True, "count": 45}

    monkeypatch.setattr(gt, "_count_leads_impl", fake_count)
    return client


# ---------------------------------------------------------------------------
# set_monthly_goal
# ---------------------------------------------------------------------------


class TestSetMonthlyGoal:
    @pytest.mark.asyncio
    async def test_set_success(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1",
            year=2026,
            month=5,
            metric="sicak_lead",
            target_value=100,
            reason="Q2 buyume planlamasi",
        )
        assert result["success"] is True
        fake_doc_client.set_document.assert_called_once()
        doc_id, data, *_ = fake_doc_client.set_document.call_args.args
        assert doc_id == "2026-05"
        assert data["metric"] == "sicak_lead"
        assert data["target_value"] == 100
        assert data["year"] == 2026 and data["month"] == 5
        assert data["reason"] == "Q2 buyume planlamasi"
        assert "created_at" in data and "updated_at" in data
        assert fake_doc_client.set_document.call_args.kwargs.get("merge") is True

    @pytest.mark.asyncio
    async def test_set_invalid_metric(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1", year=2026, month=5,
            metric="bogus", target_value=10, reason="valid reason",
        )
        assert result["success"] is False
        assert "metric" in result["error"].lower()
        fake_doc_client.set_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_year_out_of_range(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1", year=2020, month=5,
            metric="sicak_lead", target_value=10, reason="valid reason",
        )
        assert result["success"] is False
        assert "year" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_set_month_out_of_range(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1", year=2026, month=13,
            metric="sicak_lead", target_value=10, reason="valid reason",
        )
        assert result["success"] is False
        assert "month" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_set_target_zero(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1", year=2026, month=5,
            metric="sicak_lead", target_value=0, reason="valid reason",
        )
        assert result["success"] is False
        assert "target_value" in result["error"]

    @pytest.mark.asyncio
    async def test_set_short_reason(self, fake_doc_client):
        result = await gt._set_monthly_goal_impl(
            business_id="biz1", year=2026, month=5,
            metric="sicak_lead", target_value=10, reason="x",
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_monthly_progress
# ---------------------------------------------------------------------------


class TestGetMonthlyProgress:
    @pytest.mark.asyncio
    async def test_without_goal(self, fake_doc_client):
        fake_doc_client.get_document.return_value = None
        result = await gt._get_monthly_progress_impl(
            business_id="biz1", year=2026, month=5,
        )
        assert result["success"] is True
        assert result["data"] is None
        assert "hedef belirlenmedi" in result["summary_tr"]

    @pytest.mark.asyncio
    async def test_with_goal_on_track(self, fake_doc_client, monkeypatch):
        # Today: day 28 of a 30-day month, target 50, achieved 45
        # expected_pct ~93.3, progress_pct = 90 -> NOT on track
        # Use achieved 48 to be on track
        fake_doc_client.get_document.return_value = {
            "metric": "sicak_lead",
            "target_value": 50,
            "year": 2026,
            "month": 5,
            "reason": "test",
        }

        async def fake_count(**_kwargs):
            return {"success": True, "count": 48}

        monkeypatch.setattr(gt, "_count_leads_impl", fake_count)

        # Force "today" to day 15 of May 2026 (May has 31 days)
        class _FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 5, 15)

        monkeypatch.setattr(gt, "date", _FakeDate)

        result = await gt._get_monthly_progress_impl(
            business_id="biz1", year=2026, month=5,
        )
        assert result["success"] is True
        data = result["data"]
        assert data["metric"] == "sicak_lead"
        assert data["target"] == 50
        assert data["current"] == 48
        assert data["days_elapsed"] == 15
        assert data["days_remaining"] == 31 - 15
        # progress 96% vs expected ~48% -> on track
        assert data["on_track"] is True

    @pytest.mark.asyncio
    async def test_with_goal_behind(self, fake_doc_client, monkeypatch):
        fake_doc_client.get_document.return_value = {
            "metric": "yeni_lead",
            "target_value": 100,
            "year": 2026,
            "month": 5,
            "reason": "test",
        }

        async def fake_count(**_kwargs):
            return {"success": True, "count": 5}

        monkeypatch.setattr(gt, "_count_leads_impl", fake_count)

        class _FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 5, 25)

        monkeypatch.setattr(gt, "date", _FakeDate)

        result = await gt._get_monthly_progress_impl(
            business_id="biz1", year=2026, month=5,
        )
        data = result["data"]
        # progress 5% vs expected ~80% -> NOT on track
        assert data["on_track"] is False
        assert data["days_remaining"] == 31 - 25
        # daily_rate_needed = (100-5)/6
        assert data["daily_rate_needed"] == pytest.approx(95 / 6, rel=0.01)

    @pytest.mark.asyncio
    async def test_division_by_zero_protection(
        self, fake_doc_client, monkeypatch
    ):
        """Past month: days_remaining = 0 -> daily_rate_needed = 0."""
        fake_doc_client.get_document.return_value = {
            "metric": "kazanildi",
            "target_value": 10,
            "year": 2026,
            "month": 4,
            "reason": "test",
        }

        async def fake_count(**_kwargs):
            return {"success": True, "count": 3}

        monkeypatch.setattr(gt, "_count_leads_impl", fake_count)

        class _FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 5, 15)

        monkeypatch.setattr(gt, "date", _FakeDate)

        result = await gt._get_monthly_progress_impl(
            business_id="biz1", year=2026, month=4,
        )
        assert result["success"] is True
        assert result["data"]["daily_rate_needed"] == 0.0
        assert result["data"]["days_remaining"] == 0

    @pytest.mark.asyncio
    async def test_default_year_month_is_today(
        self, fake_doc_client, monkeypatch
    ):
        fake_doc_client.get_document.return_value = None

        class _FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 7, 10)

        monkeypatch.setattr(gt, "date", _FakeDate)

        await gt._get_monthly_progress_impl(business_id="biz1")
        fake_doc_client.get_document.assert_called_with("2026-07")


# ---------------------------------------------------------------------------
# list_goals
# ---------------------------------------------------------------------------


class TestListGoals:
    @pytest.mark.asyncio
    async def test_list_success(self, fake_doc_client, monkeypatch):
        fake_doc_client.list_documents.return_value = [
            {
                "metric": "sicak_lead",
                "target_value": 50,
                "year": 2026,
                "month": 4,
                "reason": "r",
            },
            {
                "metric": "kazanildi",
                "target_value": 10,
                "year": 2026,
                "month": 5,
                "reason": "r",
            },
        ]

        async def fake_count(**_kwargs):
            return {"success": True, "count": 60}

        monkeypatch.setattr(gt, "_count_leads_impl", fake_count)

        result = await gt._list_goals_impl(business_id="biz1", limit=12)
        assert result["success"] is True
        assert len(result["data"]) == 2
        # Sorted desc by (year, month)
        assert result["data"][0]["month"] == 5
        assert result["data"][1]["month"] == 4
        # achieved=60, target=50 -> success True
        assert result["data"][1]["achieved"] == 60
        assert result["data"][1]["success"] is True


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


def test_get_goal_tools_returns_three():
    tools = gt.get_goal_tools()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"set_monthly_goal", "get_monthly_progress", "list_goals"}
