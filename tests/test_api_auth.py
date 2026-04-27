"""
/task endpoint kimlik doğrulama testleri.

Auth davranışı:
- MIND_AGENT_API_KEY env var'ı SET değilse → legacy mode, auth bypass edilir
  (geriye uyumluluk için; deploy sonrası env set edilince enforce başlar).
- MIND_AGENT_API_KEY SET ise:
    - Authorization header yoksa → 401
    - Bearer dışı şema (Basic, vb.) → 401
    - Yanlış bearer → 401
    - Doğru bearer → handler'a geçer (200 stream başlar)
- /health ve /capabilities her zaman auth-free.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

# api.py import edilirken OPENAI_API_KEY gerekiyor (settings load).
os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

import pytest
from fastapi.testclient import TestClient

from src.app.api import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_orchestrator():
    """
    run_orchestrator_async'i HER testte otomatik mock'lar.
    Auth check'i gerçek dünyada orchestrator'dan ÖNCE çalışır;
    auth başarısız olunca orchestrator hiç çağrılmaz.
    Bu fixture testlerin yanlışlıkla gerçek API'ye gitmesini engeller.
    """
    async def fake_run(*args, **kwargs):
        return ("fake-output", "fake-log-path")

    with patch("src.app.api.run_orchestrator_async", new=AsyncMock(side_effect=fake_run)):
        yield


# ---------------------------------------------------------------------------
# Public endpoints — auth gerektirmez
# ---------------------------------------------------------------------------


def test_health_no_auth_needed(client, monkeypatch):
    """MIND_AGENT_API_KEY set olsa bile /health açık olmalı."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "any-key")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_capabilities_no_auth_needed(client, monkeypatch):
    """MIND_AGENT_API_KEY set olsa bile /capabilities açık olmalı."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "any-key")
    response = client.get("/capabilities")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Legacy mode — env yoksa auth bypass
# ---------------------------------------------------------------------------


def test_task_no_auth_required_when_key_unset(client, monkeypatch):
    """MIND_AGENT_API_KEY env yoksa /task auth-siz çalışmalı (geriye uyum)."""
    monkeypatch.delenv("MIND_AGENT_API_KEY", raising=False)
    response = client.post("/task", json={"task": "hello"})
    # Legacy mode: stream başlar, 200 döner. (İçerik mock olduğu için patlamaz.)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Auth enforced mode — env varsa kontrol et
# ---------------------------------------------------------------------------


def test_task_returns_401_when_no_authorization_header(client, monkeypatch):
    """Env set + Authorization header yok → 401."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123")
    response = client.post("/task", json={"task": "hello"})
    assert response.status_code == 401


def test_task_returns_401_when_basic_scheme(client, monkeypatch):
    """Env set + Basic auth (Bearer değil) → 401."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123")
    response = client.post(
        "/task",
        json={"task": "hello"},
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


def test_task_returns_401_when_wrong_bearer(client, monkeypatch):
    """Env set + Bearer ama yanlış key → 401."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123")
    response = client.post(
        "/task",
        json={"task": "hello"},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


def test_task_returns_401_when_empty_bearer(client, monkeypatch):
    """Env set + 'Bearer ' (boş key) → 401."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123")
    response = client.post(
        "/task",
        json={"task": "hello"},
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 401


def test_task_passes_with_correct_bearer(client, monkeypatch):
    """Env set + doğru Bearer → handler'a geçer (200 stream)."""
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123")
    response = client.post(
        "/task",
        json={"task": "hello"},
        headers={"Authorization": "Bearer secret-123"},
    )
    assert response.status_code == 200


def test_task_constant_time_comparison(client, monkeypatch):
    """
    Auth check secrets.compare_digest kullanmalı (timing attack koruması).
    Bu testi unit-level değil davranışsal yapıyoruz: yanlış key
    'doğru key prefix'i' olsa bile 401 döner.
    """
    monkeypatch.setenv("MIND_AGENT_API_KEY", "secret-123-suffix")
    response = client.post(
        "/task",
        json={"task": "hello"},
        headers={"Authorization": "Bearer secret-123"},  # sadece prefix
    )
    assert response.status_code == 401
