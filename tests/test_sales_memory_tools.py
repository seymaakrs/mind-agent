"""Sales memory tools — Firestore-backed persistent notes for Sales Director."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.tools.sales import memory_tools  # noqa: E402
from src.tools.sales.memory_tools import (  # noqa: E402
    _get_sales_memory_impl,
    _update_sales_memory_impl,
    get_memory_tools,
)


class TestGetSalesMemory:
    @pytest.mark.asyncio
    async def test_returns_existing_notes(self, monkeypatch):
        doc_client = MagicMock()
        doc_client.get_document.return_value = {
            "notes": "onceki seans notlari",
            "updated_at": "2026-05-20T12:00:00+00:00",
        }
        monkeypatch.setattr(
            memory_tools, "get_document_client", lambda _: doc_client
        )
        result = await _get_sales_memory_impl(business_id="biz1")
        assert result["success"] is True
        assert result["exists"] is True
        assert result["notes"] == "onceki seans notlari"
        assert result["business_id"] == "biz1"
        doc_client.get_document.assert_called_once_with("notes")

    @pytest.mark.asyncio
    async def test_no_notes_returns_empty(self, monkeypatch):
        doc_client = MagicMock()
        doc_client.get_document.return_value = None
        monkeypatch.setattr(
            memory_tools, "get_document_client", lambda _: doc_client
        )
        result = await _get_sales_memory_impl(business_id="biz1")
        assert result["success"] is True
        assert result["exists"] is False
        assert result["notes"] == ""

    @pytest.mark.asyncio
    async def test_missing_business_id(self, monkeypatch):
        monkeypatch.delenv("SALES_DIRECTOR_BUSINESS_ID", raising=False)
        result = await _get_sales_memory_impl(business_id=None)
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_env_fallback(self, monkeypatch):
        doc_client = MagicMock()
        doc_client.get_document.return_value = {"notes": "envli", "updated_at": "x"}
        monkeypatch.setenv("SALES_DIRECTOR_BUSINESS_ID", "env-biz")
        monkeypatch.setattr(
            memory_tools, "get_document_client", lambda _: doc_client
        )
        result = await _get_sales_memory_impl(business_id=None)
        assert result["success"] is True
        assert result["business_id"] == "env-biz"


class TestUpdateSalesMemory:
    @pytest.mark.asyncio
    async def test_updates_and_returns_chars(self, monkeypatch):
        doc_client = MagicMock()
        monkeypatch.setattr(
            memory_tools, "get_document_client", lambda _: doc_client
        )
        result = await _update_sales_memory_impl(notes="yeni notlar", business_id="biz1")
        assert result["success"] is True
        assert result["chars"] == len("yeni notlar")
        assert result["business_id"] == "biz1"
        doc_client.set_document.assert_called_once()
        args, kwargs = doc_client.set_document.call_args
        # set_document(doc_id, payload, merge=True)
        assert args[0] == "notes"
        assert args[1]["notes"] == "yeni notlar"
        assert "updated_at" in args[1]
        assert kwargs.get("merge") is True

    @pytest.mark.asyncio
    async def test_missing_business_id(self, monkeypatch):
        monkeypatch.delenv("SALES_DIRECTOR_BUSINESS_ID", raising=False)
        result = await _update_sales_memory_impl(notes="x", business_id=None)
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


class TestRegistration:
    def test_get_memory_tools_exposes_both(self):
        names = {t.name for t in get_memory_tools()}
        assert names == {"get_sales_memory", "update_sales_memory"}
