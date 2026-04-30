"""Sales webhook receiver tests.

Cover:
- Signature verification (HMAC-SHA256)
- Idempotency (X-Zernio-Delivery-Id de-dup, leadgen_id de-dup)
- Event filtering (only message.received / comment.received dispatched)
- Meta verify GET handshake (hub.challenge)
- Background dispatch is scheduled but tolerated when env not configured
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app import sales_webhooks


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Fresh FastAPI app + isolated idempotency cache for each test."""
    sales_webhooks._reset_idempotency_cache()
    app = FastAPI()
    app.include_router(sales_webhooks.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_orchestrator_runner(monkeypatch: pytest.MonkeyPatch):
    """Avoid loading the real orchestrator (Firebase, OpenAI) during webhook tests."""
    async def _noop(**kwargs):
        return None

    # Patch the deferred import target
    import sys
    import types

    fake = types.ModuleType("src.app.orchestrator_runner")
    fake.run_orchestrator_async = _noop  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.app.orchestrator_runner", fake)
    yield


# ---------------------------------------------------------------------------
# Zernio webhook
# ---------------------------------------------------------------------------


class TestZernioWebhook:
    SECRET = "z-secret-1"

    def test_unsigned_request_rejected_in_prod_mode(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No DRY_RUN, no signature, no secret -> 503 (config error)
        monkeypatch.delenv("DRY_RUN", raising=False)
        monkeypatch.delenv("ZERNIO_WEBHOOK_SECRET", raising=False)
        body = json.dumps({"event": "message.received", "data": {}})
        resp = client.post("/sales/webhook/zernio", data=body)
        assert resp.status_code == 503

    def test_invalid_signature_returns_401(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", self.SECRET)
        body = json.dumps({"event": "message.received", "data": {}}).encode()
        resp = client.post(
            "/sales/webhook/zernio",
            content=body,
            headers={"X-Zernio-Signature": "sha256=deadbeef"},
        )
        assert resp.status_code == 401

    def test_valid_signature_message_received_dispatched(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", self.SECRET)
        body = json.dumps(
            {
                "event": "message.received",
                "data": {
                    "platform": "instagram",
                    "account_id": "acc_1",
                    "sender_id": "u_42",
                    "thread_id": "t_xyz",
                    "text": "Merhaba, fiyat ne?",
                },
            }
        ).encode()
        resp = client.post(
            "/sales/webhook/zernio",
            content=body,
            headers={"X-Zernio-Signature": _sign(body, self.SECRET)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["dispatched"] is True

    def test_unsupported_event_acknowledged_but_not_dispatched(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", self.SECRET)
        body = json.dumps({"event": "message.delivered", "data": {}}).encode()
        resp = client.post(
            "/sales/webhook/zernio",
            content=body,
            headers={"X-Zernio-Signature": _sign(body, self.SECRET)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dispatched"] is False
        assert data["event"] == "message.delivered"

    def test_idempotent_replay_returns_deduped(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", self.SECRET)
        body = json.dumps({"event": "message.received", "data": {}}).encode()
        sig = _sign(body, self.SECRET)
        h1 = client.post(
            "/sales/webhook/zernio",
            content=body,
            headers={
                "X-Zernio-Signature": sig,
                "X-Zernio-Delivery-Id": "deliv-1",
            },
        )
        h2 = client.post(
            "/sales/webhook/zernio",
            content=body,
            headers={
                "X-Zernio-Signature": sig,
                "X-Zernio-Delivery-Id": "deliv-1",
            },
        )
        assert h1.status_code == 200
        assert h2.status_code == 200
        assert h2.json()["deduped"] is True


# ---------------------------------------------------------------------------
# Meta Lead webhook
# ---------------------------------------------------------------------------


class TestMetaLeadWebhook:
    SECRET = "meta-secret"

    def test_verify_handshake_succeeds_with_correct_token(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("META_VERIFY_TOKEN", "vt-123")
        resp = client.get(
            "/sales/webhook/meta-lead",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "vt-123",
                "hub.challenge": "the-challenge",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "the-challenge"

    def test_verify_handshake_rejects_wrong_token(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("META_VERIFY_TOKEN", "vt-123")
        resp = client.get(
            "/sales/webhook/meta-lead",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "x",
            },
        )
        assert resp.status_code == 403

    def test_lead_payload_dispatched(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("META_WEBHOOK_SECRET", self.SECRET)
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page-1",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg-42",
                                "page_id": "page-1",
                                "form_id": "f-1",
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode()
        resp = client.post(
            "/sales/webhook/meta-lead",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body, self.SECRET)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dispatched"] is True
        assert data["leadgen_id"] == "lg-42"

    def test_duplicate_leadgen_id_deduped(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("META_WEBHOOK_SECRET", self.SECRET)
        payload = {
            "entry": [
                {
                    "changes": [
                        {"value": {"leadgen_id": "dup-1"}}
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, self.SECRET)
        first = client.post(
            "/sales/webhook/meta-lead",
            content=body,
            headers={"X-Hub-Signature-256": sig},
        )
        second = client.post(
            "/sales/webhook/meta-lead",
            content=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["deduped"] is True
