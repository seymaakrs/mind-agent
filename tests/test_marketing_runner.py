"""Tests for Marketing Dispatcher runner — offline wiring + logic tests."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


os.environ.setdefault("OPENAI_API_KEY", "test")


class TestResolveMaxIterations:
    def test_run_once_true_returns_one(self, monkeypatch):
        from src.agents.marketing.runner import _resolve_max_iterations

        monkeypatch.setenv("RUN_ONCE", "true")
        assert _resolve_max_iterations() == 1

    def test_run_once_false_returns_none(self, monkeypatch):
        from src.agents.marketing.runner import _resolve_max_iterations

        monkeypatch.setenv("RUN_ONCE", "false")
        assert _resolve_max_iterations() is None

    def test_run_once_unset_returns_none(self, monkeypatch):
        from src.agents.marketing.runner import _resolve_max_iterations

        monkeypatch.delenv("RUN_ONCE", raising=False)
        assert _resolve_max_iterations() is None

    def test_run_once_yes_returns_one(self, monkeypatch):
        from src.agents.marketing.runner import _resolve_max_iterations

        monkeypatch.setenv("RUN_ONCE", "yes")
        assert _resolve_max_iterations() == 1


class TestGetActiveBusinessIds:
    @pytest.mark.asyncio
    async def test_returns_empty_when_firestore_unreachable(self):
        from src.agents.marketing import runner

        # Patch the import inside the function
        with patch("src.infra.firebase_client.get_document_client") as mock_client:
            mock_client.side_effect = RuntimeError("firestore down")
            result = await runner._get_active_business_ids()
            assert result == []

    @pytest.mark.asyncio
    async def test_filters_archived_and_deleted(self):
        from src.agents.marketing import runner

        mock_biz_client = MagicMock()
        mock_biz_client.query_documents.return_value = [
            {"documentId": "biz1", "status": "approved"},
            {"documentId": "biz2", "status": "archived"},  # skip
            {"documentId": "biz3", "status": "deleted"},   # skip
            {"documentId": "biz4"},  # no status, kept
        ]
        with patch(
            "src.infra.firebase_client.get_document_client",
            return_value=mock_biz_client,
        ):
            ids = await runner._get_active_business_ids()
        assert "biz1" in ids
        assert "biz4" in ids
        assert "biz2" not in ids
        assert "biz3" not in ids


class TestBusinessHasPlannedPostToday:
    @pytest.mark.asyncio
    async def test_returns_true_when_planned_post_today(self, monkeypatch):
        from datetime import datetime, timezone

        from src.agents.marketing import runner

        today = datetime.now(timezone.utc).date().isoformat()

        mock_plans_client = MagicMock()
        mock_plans_client.query_documents.return_value = [
            {
                "status": "active",
                "posts": [
                    {"scheduled_date": today, "status": "planned"},
                ],
            }
        ]
        with patch(
            "src.infra.firebase_client.get_document_client",
            return_value=mock_plans_client,
        ):
            result = await runner._business_has_planned_post_today("biz1")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_active_plan(self):
        from src.agents.marketing import runner

        mock_plans_client = MagicMock()
        mock_plans_client.query_documents.return_value = []
        with patch(
            "src.infra.firebase_client.get_document_client",
            return_value=mock_plans_client,
        ):
            result = await runner._business_has_planned_post_today("biz1")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_planned_today(self):
        from src.agents.marketing import runner

        mock_plans_client = MagicMock()
        mock_plans_client.query_documents.return_value = [
            {
                "status": "active",
                "posts": [
                    {"scheduled_date": "2020-01-01", "status": "planned"},
                ],
            }
        ]
        with patch(
            "src.infra.firebase_client.get_document_client",
            return_value=mock_plans_client,
        ):
            result = await runner._business_has_planned_post_today("biz1")
        assert result is False

    @pytest.mark.asyncio
    async def test_defensive_true_on_firestore_error(self):
        """Hata olunca defansif True don — Orchestrator karar versin."""
        from src.agents.marketing import runner

        with patch(
            "src.infra.firebase_client.get_document_client",
            side_effect=RuntimeError("network"),
        ):
            result = await runner._business_has_planned_post_today("biz1")
        assert result is True  # defansif


class TestTick:
    @pytest.mark.asyncio
    async def test_tick_returns_summary_when_no_businesses(self):
        from src.agents.marketing import runner

        with patch.object(
            runner, "_get_active_business_ids", new=AsyncMock(return_value=[])
        ):
            summary = await runner.tick()
        assert summary["businesses_total"] == 0
        assert summary["dispatched"] == 0


class TestLoopOneShot:
    @pytest.mark.asyncio
    async def test_loop_max_iter_one_exits_after_tick(self):
        from src.agents.marketing import runner

        mock_tick = AsyncMock(return_value={"businesses_total": 0, "dispatched": 0})
        with patch.object(runner, "tick", new=mock_tick):
            await runner.loop(max_iterations=1)
        mock_tick.assert_awaited_once()
