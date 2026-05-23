"""H-1 — Sales REST API contract snapshot.

Portal (mind-id) Sales sekmesi bu 4 endpoint'i dogrudan parse eder.
Response shape sessizce drift ederse UI kirilir. Bu testler:

* her endpoint icin **required key set** dondurur
* 401 unauthorized davranisini ve 503 ``SALES_API_TOKEN`` yok davranisini
  pinler
* downstream'in bagli oldugu yapinin (``success``, ``error``) shim'lerini
  hem basari hem hata yolunda kontrol eder

Sirf shape'i dondurmak icin; gercek NocoDB veya Firestore call'lari
``monkeypatch`` ile mock'lanir. Faz B (Sales Director) hardening seti
icinde calistirilmasi beklenir.
"""
from __future__ import annotations

import pytest

pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Endpoint required-key contracts. Update these together with the route +
# any portal consumer (mind-id /api/sales/[...path]/route.ts) in a single PR.
#
# These names match the actual return shape of reporting_tools._*_impl
# (cross-verified against mind-id components/businesses/tabs/sales-tab.tsx
# during ADIM 3 hardening — both sides agree on the names below).
LEADS_COUNT_REQUIRED = {"success", "count"}
LEADS_FUNNEL_REQUIRED = {"success", "data"}  # portal reads .data, not .stages
OUTREACH_STATUS_REQUIRED = {"success", "sent_today", "daily_limit", "remaining"}
OUTREACH_HEALTH_REQUIRED = {"success", "paused", "active"}


@pytest.fixture
def app_client(monkeypatch):
    """Build a FastAPI app with sales_api router and stub the *_impl calls."""
    monkeypatch.setenv("SALES_API_TOKEN", "test-token-xyz")

    from src.app import sales_api

    async def _stub_count(**_):
        return {"success": True, "count": 42, "filters_applied": {}}

    async def _stub_funnel(**_):
        return {
            "success": True,
            "type": "funnel",
            "schema": "funnel",
            "data": [
                {"asama": "Yeni", "count": 12},
                {"asama": "Sicak", "count": 5},
            ],
            "total": 17,
        }

    async def _stub_outreach_status():
        return {
            "success": True,
            "sent_today": 18,
            "daily_limit": 240,
            "remaining": 222,
            "percent_used": 7.5,
            "sent_last_hour": 3,
        }

    async def _stub_outreach_health():
        return {
            "success": True,
            "configured": True,
            "active": True,
            "paused": False,
            "reason": None,
        }

    monkeypatch.setattr(sales_api, "_count_leads_impl", _stub_count)
    monkeypatch.setattr(sales_api, "_lead_funnel_impl", _stub_funnel)
    monkeypatch.setattr(sales_api, "_outreach_status_impl", _stub_outreach_status)
    monkeypatch.setattr(sales_api, "_outreach_health_impl", _stub_outreach_health)

    app = FastAPI()
    app.include_router(sales_api.router)
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer test-token-xyz"}


def test_leads_count_returns_required_keys(app_client):
    r = app_client.get("/sales/leads/count", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert LEADS_COUNT_REQUIRED <= set(body.keys()), (
        f"required keys missing. Got: {sorted(body.keys())}"
    )
    assert body["success"] is True
    assert isinstance(body["count"], int)


def test_leads_funnel_returns_required_keys_and_stage_shape(app_client):
    r = app_client.get("/sales/leads/funnel", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert LEADS_FUNNEL_REQUIRED <= set(body.keys())
    assert isinstance(body["data"], list) and body["data"], "data must be a non-empty list"
    for stage in body["data"]:
        assert {"asama", "count"} <= set(stage.keys()), (
            f"funnel stage missing keys. Got: {sorted(stage.keys())}"
        )


def test_outreach_status_returns_required_keys(app_client):
    r = app_client.get("/sales/outreach/status", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert OUTREACH_STATUS_REQUIRED <= set(body.keys())


def test_outreach_health_returns_required_keys(app_client):
    r = app_client.get("/sales/outreach/health", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert OUTREACH_HEALTH_REQUIRED <= set(body.keys())
    assert isinstance(body["paused"], bool)


@pytest.mark.parametrize(
    "path",
    [
        "/sales/leads/count",
        "/sales/leads/funnel",
        "/sales/outreach/status",
        "/sales/outreach/health",
    ],
)
def test_401_without_bearer(app_client, path):
    r = app_client.get(path)
    assert r.status_code == 401, (
        f"{path} must reject unauthenticated requests; got {r.status_code}"
    )


@pytest.mark.parametrize(
    "path",
    ["/sales/leads/count", "/sales/leads/funnel"],
)
def test_401_with_wrong_token(app_client, path):
    r = app_client.get(path, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_503_when_token_env_missing(monkeypatch):
    """SALES_API_TOKEN env yoksa endpoint disabled (503), 200 dondurmemeli."""
    monkeypatch.delenv("SALES_API_TOKEN", raising=False)

    from src.app import sales_api

    app = FastAPI()
    app.include_router(sales_api.router)
    client = TestClient(app)
    r = client.get("/sales/leads/count", headers=_auth())
    assert r.status_code == 503, (
        f"With SALES_API_TOKEN unset, endpoint must return 503; got {r.status_code}"
    )


def test_502_when_underlying_call_fails(monkeypatch):
    """NocoDB read fail -> 502, success=false dict shape leak etmemeli."""
    monkeypatch.setenv("SALES_API_TOKEN", "tok")

    from src.app import sales_api

    async def _fail(**_):
        return {"success": False, "error": "NocoDB timeout"}

    monkeypatch.setattr(sales_api, "_count_leads_impl", _fail)
    app = FastAPI()
    app.include_router(sales_api.router)
    client = TestClient(app)
    r = client.get("/sales/leads/count", headers={"Authorization": "Bearer tok"})
    assert r.status_code == 502
    assert "NocoDB timeout" in r.json().get("detail", "")
