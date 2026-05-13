"""Tests for src.tools.brand — load/save/fetch/update with Firestore mock."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.infra.brand_identity import BrandBasics, BrandIdentity, BrandVisual
from src.tools import brand as brand_mod


@pytest.fixture
def mock_doc_client(monkeypatch):
    """Mock get_document_client to return a controllable client."""
    client = MagicMock()
    client.get_document.return_value = None
    client.set_document.return_value = {"document_id": "v1"}
    monkeypatch.setattr(brand_mod, "get_document_client", lambda path: client)
    return client


class TestLoadBrandIdentity:
    def test_returns_none_when_empty_business_id(self):
        assert brand_mod.load_brand_identity("") is None

    def test_returns_none_when_doc_missing(self, mock_doc_client):
        mock_doc_client.get_document.return_value = None
        assert brand_mod.load_brand_identity("abc") is None

    def test_returns_brand_identity_when_doc_exists(self, mock_doc_client):
        mock_doc_client.get_document.return_value = {
            "business_id": "abc",
            "schema_version": 1,
            "basics": {"name": "Mind-id"},
            "visual": {"primary_colors": ["#C1FF72"]},
            "documentId": "v1",  # Firestore adds this, helper strips
        }
        bi = brand_mod.load_brand_identity("abc")
        assert bi is not None
        assert bi.basics.name == "Mind-id"
        assert bi.visual.primary_colors == ["#C1FF72"]

    def test_returns_none_on_parse_error(self, mock_doc_client):
        mock_doc_client.get_document.return_value = {"invalid": "data"}
        assert brand_mod.load_brand_identity("abc") is None


class TestSaveBrandIdentity:
    def test_writes_to_firestore(self, mock_doc_client):
        bi = BrandIdentity(business_id="abc", basics=BrandBasics(name="Mind-id"))
        result = brand_mod.save_brand_identity(bi)
        assert result["success"] is True
        assert result["business_id"] == "abc"
        mock_doc_client.set_document.assert_called_once()
        doc_id, data = mock_doc_client.set_document.call_args.args[:2]
        assert doc_id == "v1"
        assert data["basics"]["name"] == "Mind-id"

    def test_handles_save_error(self, mock_doc_client):
        mock_doc_client.set_document.side_effect = RuntimeError("firestore down")
        bi = BrandIdentity(business_id="abc")
        result = brand_mod.save_brand_identity(bi)
        assert result["success"] is False
        assert "firestore down" in result["error"]


class TestBrandIdentityExists:
    def test_true_when_loaded(self, mock_doc_client):
        mock_doc_client.get_document.return_value = {
            "business_id": "abc",
            "schema_version": 1,
        }
        assert brand_mod.brand_identity_exists("abc") is True

    def test_false_when_missing(self, mock_doc_client):
        mock_doc_client.get_document.return_value = None
        assert brand_mod.brand_identity_exists("abc") is False


class TestFetchBrandIdentityImpl:
    @pytest.mark.asyncio
    async def test_returns_error_on_empty_id(self):
        data = await brand_mod._fetch_brand_identity_impl("")
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_exists_false_when_no_doc(self, mock_doc_client):
        mock_doc_client.get_document.return_value = None
        data = await brand_mod._fetch_brand_identity_impl("abc")
        assert data["success"] is True
        assert data["exists"] is False

    @pytest.mark.asyncio
    async def test_returns_full_data_when_exists(self, mock_doc_client):
        mock_doc_client.get_document.return_value = {
            "business_id": "abc",
            "schema_version": 1,
            "basics": {"name": "Mind-id"},
            "visual": {"primary_colors": ["#FFF"], "visual_style": "modern"},
        }
        data = await brand_mod._fetch_brand_identity_impl("abc")
        assert data["success"] is True
        assert data["exists"] is True
        assert data["basics"]["name"] == "Mind-id"
        assert "prompt_summary" in data
        assert "Mind-id" in data["prompt_summary"]


class TestUpdateBrandIdentityImpl:
    @pytest.mark.asyncio
    async def test_creates_new_when_no_existing(self, mock_doc_client):
        mock_doc_client.get_document.return_value = None
        data = await brand_mod._update_brand_identity_impl(
            "abc",
            fields={"basics": {"name": "Mind-id"}},
            source="ai_synthesis",
        )
        assert data["success"] is True
        saved = mock_doc_client.set_document.call_args.args[1]
        assert saved["basics"]["name"] == "Mind-id"
        assert saved["source"] == "ai_synthesis"

    @pytest.mark.asyncio
    async def test_merges_with_existing(self, mock_doc_client):
        mock_doc_client.get_document.return_value = {
            "business_id": "abc",
            "schema_version": 1,
            "basics": {"name": "Mind-id", "industry": "B2B"},
            "visual": {"primary_colors": ["#FFF"]},
        }
        data = await brand_mod._update_brand_identity_impl(
            "abc", fields={"basics": {"tagline": "AI"}}
        )
        assert data["success"] is True
        saved = mock_doc_client.set_document.call_args.args[1]
        # Shallow merge in basics: name + industry korunmus, tagline eklenmis
        assert saved["basics"]["name"] == "Mind-id"
        assert saved["basics"]["industry"] == "B2B"
        assert saved["basics"]["tagline"] == "AI"
        # visual da korunmus
        assert saved["visual"]["primary_colors"] == ["#FFF"]

    @pytest.mark.asyncio
    async def test_rejects_invalid_data(self, mock_doc_client):
        mock_doc_client.get_document.return_value = None
        data = await brand_mod._update_brand_identity_impl(
            "abc", fields={"visual": {"primary_colors": ["red"]}}
        )
        assert data["success"] is False
        assert "validation" in data["error"].lower()


class TestToolRegistration:
    def test_get_brand_tools_returns_both(self):
        tools = brand_mod.get_brand_tools()
        names = {t.name for t in tools}
        assert names == {"fetch_brand_identity", "update_brand_identity"}
