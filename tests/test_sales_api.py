"""Sales REST API endpoint testleri.

Portal (mind-id) bu endpoint'leri direkt cagirir — LLM atlanir, deterministik
rapor. Bearer token zorunlu.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("SALES_API_TOKEN", "secret-test-token")
    from src.app.api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def disabled_client(monkeypatch):
    """Token env yoksa 503 dondurmeli."""
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.delenv("SALES_API_TOKEN", raising=False)
    from src.app.api import app

    with TestClient(app) as c:
        yield c


class TestAuth:
    def test_missing_token_returns_503_when_env_not_set(self, disabled_client):
        r = disabled_client.get("/sales/leads/count")
        assert r.status_code == 503
        assert "SALES_API_TOKEN" in r.json()["detail"]

    def test_missing_bearer_header_returns_401(self, client):
        r = client.get("/sales/leads/count")
        assert r.status_code == 401

    def test_wrong_bearer_token_returns_401(self, client):
        r = client.get(
            "/sales/leads/count",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401


class TestEndpoints:
    HEADERS = {"Authorization": "Bearer secret-test-token"}

    def test_leads_count_delegates_to_impl(self, client, monkeypatch):
        import src.app.sales_api as api

        async def fake_count(**kwargs):
            return {
                "success": True,
                "count": 42,
                "filters": kwargs,
                "summary_tr": "42 Sicak lead.",
            }

        monkeypatch.setattr(api, "_count_leads_impl", fake_count)

        r = client.get(
            "/sales/leads/count?asama=Sicak&kaynak=Meta+Ads",
            headers=self.HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 42
        assert body["filters"]["asama"] == "Sicak"
        assert body["filters"]["kaynak"] == "Meta Ads"

    def test_leads_count_502_on_impl_failure(self, client, monkeypatch):
        import src.app.sales_api as api

        async def fail(**_kwargs):
            return {"success": False, "error": "NocoDB timeout"}

        monkeypatch.setattr(api, "_count_leads_impl", fail)
        r = client.get("/sales/leads/count", headers=self.HEADERS)
        assert r.status_code == 502
        assert "NocoDB timeout" in r.json()["detail"]

    def test_outreach_health_delegates(self, client, monkeypatch):
        import src.app.sales_api as api

        async def fake_health():
            return {
                "success": True,
                "configured": True,
                "active": False,
                "paused": True,
                "reason": "Reply rate %2.1",
            }

        monkeypatch.setattr(api, "_outreach_health_impl", fake_health)
        r = client.get("/sales/outreach/health", headers=self.HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["paused"] is True
        assert body["active"] is False
