"""Tests for src.tools.sales.memory_tools — Firestore mocked."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.tools.sales import memory_tools as mt


@pytest.fixture
def mock_doc_client(monkeypatch):
    """Mock get_document_client. Tracks calls per-collection-path."""
    clients_by_path: dict[str, MagicMock] = {}

    def factory(path: str) -> MagicMock:
        if path not in clients_by_path:
            c = MagicMock()
            c.get_document.return_value = None
            c.set_document.return_value = {"documentId": "x"}
            c.delete_document.return_value = True
            c.list_documents.return_value = []
            c._path = path
            clients_by_path[path] = c
        return clients_by_path[path]

    monkeypatch.setattr(mt, "get_document_client", factory)
    return clients_by_path


# ---------------------------------------------------------------------------
# save_sales_memory
# ---------------------------------------------------------------------------


class TestSaveSalesMemory:
    @pytest.mark.asyncio
    async def test_success(self, mock_doc_client):
        res = await mt._save_sales_memory_impl(
            business_id="abc",
            category="decisions",
            key="pause_slowdays",
            value="Slowdays kampanyası duraklatıldı 3 gün",
            reason="Bekçi RED alarmı geldi",
        )
        assert res["success"] is True
        assert res["category"] == "decisions"
        path = "businesses/abc/sales_memory/decisions/notes"
        assert path in mock_doc_client
        c = mock_doc_client[path]
        c.set_document.assert_called_once()
        doc_id, data = c.set_document.call_args.args[:2]
        assert doc_id == "pause_slowdays"
        assert data["value"].startswith("Slowdays")
        assert data["category"] == "decisions"
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_invalid_category(self, mock_doc_client):
        res = await mt._save_sales_memory_impl(
            business_id="abc",
            category="bogus",
            key="kx",
            value="some value here",
            reason="some reason",
        )
        assert res["success"] is False
        assert "Geçersiz category" in res["error"]

    @pytest.mark.asyncio
    async def test_value_too_short(self, mock_doc_client):
        res = await mt._save_sales_memory_impl(
            business_id="abc",
            category="learnings",
            key="kx",
            value="hi",
            reason="valid reason here",
        )
        assert res["success"] is False
        assert "value" in res["error"]

    @pytest.mark.asyncio
    async def test_reason_too_short(self, mock_doc_client):
        res = await mt._save_sales_memory_impl(
            business_id="abc",
            category="learnings",
            key="kx",
            value="value long enough",
            reason="no",
        )
        assert res["success"] is False
        assert "reason" in res["error"]

    @pytest.mark.asyncio
    async def test_key_too_short(self, mock_doc_client):
        res = await mt._save_sales_memory_impl(
            business_id="abc",
            category="learnings",
            key="k",
            value="value long enough",
            reason="valid reason here",
        )
        assert res["success"] is False
        assert "key" in res["error"]


# ---------------------------------------------------------------------------
# get_sales_memory
# ---------------------------------------------------------------------------


class TestGetSalesMemory:
    @pytest.mark.asyncio
    async def test_with_category(self, mock_doc_client):
        # Prime the client for the decisions path
        path = "businesses/abc/sales_memory/decisions/notes"
        # touch via factory to create client
        from src.tools.sales import memory_tools as mt2
        c = mt2.get_document_client(path)
        c.list_documents.return_value = [
            {
                "documentId": "k1",
                "key": "k1",
                "value": "v1",
                "reason": "r1",
                "updated_at": "2026-05-21T00:00:00+00:00",
            }
        ]
        res = await mt._get_sales_memory_impl(
            business_id="abc", category="decisions"
        )
        assert res["success"] is True
        assert "decisions" in res["data"]
        assert res["data"]["decisions"][0]["key"] == "k1"

    @pytest.mark.asyncio
    async def test_without_category_iterates_all(self, mock_doc_client):
        from src.tools.sales import memory_tools as mt2
        # Put one note in 'preferences'
        c_pref = mt2.get_document_client(
            "businesses/abc/sales_memory/preferences/notes"
        )
        c_pref.list_documents.return_value = [
            {"documentId": "pk", "key": "pk", "value": "pv", "reason": "pr",
             "updated_at": "2026-05-21T00:00:00+00:00"},
        ]
        # Put one note in 'contacts'
        c_cont = mt2.get_document_client(
            "businesses/abc/sales_memory/contacts/notes"
        )
        c_cont.list_documents.return_value = [
            {"documentId": "ck", "key": "ck", "value": "cv", "reason": "cr",
             "updated_at": "2026-05-21T00:00:00+00:00"},
        ]
        res = await mt._get_sales_memory_impl(business_id="abc")
        assert res["success"] is True
        assert set(res["data"].keys()) == {"preferences", "contacts"}
        assert len(res["data"]["preferences"]) == 1
        assert len(res["data"]["contacts"]) == 1

    @pytest.mark.asyncio
    async def test_empty(self, mock_doc_client):
        res = await mt._get_sales_memory_impl(business_id="abc")
        assert res["success"] is True
        assert res["data"] == {}
        assert "kayıtlı hafıza yok" in res["summary_tr"]

    @pytest.mark.asyncio
    async def test_invalid_category(self, mock_doc_client):
        res = await mt._get_sales_memory_impl(
            business_id="abc", category="bogus"
        )
        assert res["success"] is False


# ---------------------------------------------------------------------------
# delete_sales_memory
# ---------------------------------------------------------------------------


class TestDeleteSalesMemory:
    @pytest.mark.asyncio
    async def test_success(self, mock_doc_client):
        from src.tools.sales import memory_tools as mt2
        path = "businesses/abc/sales_memory/decisions/notes"
        c = mt2.get_document_client(path)
        c.get_document.return_value = {
            "key": "pause_slowdays", "value": "v", "reason": "r",
        }
        res = await mt._delete_sales_memory_impl(
            business_id="abc",
            category="decisions",
            key="pause_slowdays",
            reason="Artık geçerli değil, kampanya tekrar başladı",
        )
        assert res["success"] is True
        c.delete_document.assert_called_once_with("pause_slowdays")

    @pytest.mark.asyncio
    async def test_not_found(self, mock_doc_client):
        res = await mt._delete_sales_memory_impl(
            business_id="abc",
            category="decisions",
            key="nope",
            reason="silelim bunu artık",
        )
        assert res["success"] is False
        assert "bulunamadı" in res["error"]

    @pytest.mark.asyncio
    async def test_reason_required(self, mock_doc_client):
        res = await mt._delete_sales_memory_impl(
            business_id="abc",
            category="decisions",
            key="kx",
            reason="x",
        )
        assert res["success"] is False
        assert "reason" in res["error"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_has_three_tools():
    tools = mt.get_sales_memory_tools()
    assert len(tools) == 3
    names = {getattr(t, "name", None) for t in tools}
    assert names == {"save_sales_memory", "get_sales_memory", "delete_sales_memory"}
