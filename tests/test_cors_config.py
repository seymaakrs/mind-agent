"""
CORS config testleri.

Davranis:
- CORS_ALLOWED_ORIGINS env yoksa → wildcard (*) ama allow_credentials=False
  (cookie/Authorization header otomatik gonderilemez — XSS/CSRF surface kapali).
- Env set → tam liste origin, allow_credentials=True (trusted browser client'lar
  cookie/auth header gonderebilir).
- Comma-separated parse, whitespace tolerated, bos string ignored.

Bu, OpenAI Agents SDK API'sinin sozlesmesi: production'da operator
origin listesini explicit set etmedigi surece, browser tarafindaki kimlik
bilgileri istemsiz sizmaz.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from src.app.api import get_cors_config


def test_default_when_env_not_set(monkeypatch):
    """Env yoksa wildcard ama credentials kapali."""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["*"]
    assert cfg["allow_credentials"] is False


def test_default_when_env_empty_string(monkeypatch):
    """Bos string env, env yokmus gibi davranir."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["*"]
    assert cfg["allow_credentials"] is False


def test_default_when_env_only_whitespace(monkeypatch):
    """Sadece bosluk env, default davranis."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "   ")
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["*"]
    assert cfg["allow_credentials"] is False


def test_single_origin(monkeypatch):
    """Tek origin → liste, credentials=True."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.slowdaysai.com")
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["https://app.slowdaysai.com"]
    assert cfg["allow_credentials"] is True


def test_multiple_origins_comma_separated(monkeypatch):
    """Comma-separated → liste."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.slowdaysai.com,https://admin.slowdaysai.com",
    )
    cfg = get_cors_config()
    assert cfg["allow_origins"] == [
        "https://app.slowdaysai.com",
        "https://admin.slowdaysai.com",
    ]
    assert cfg["allow_credentials"] is True


def test_whitespace_around_origins_trimmed(monkeypatch):
    """Origin'lerin etrafindaki bosluk silinir."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " https://app.slowdaysai.com ,  https://admin.slowdaysai.com  ",
    )
    cfg = get_cors_config()
    assert cfg["allow_origins"] == [
        "https://app.slowdaysai.com",
        "https://admin.slowdaysai.com",
    ]


def test_empty_items_dropped(monkeypatch):
    """Bos virgul aralari ignore edilir."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://a.com,,  ,https://b.com",
    )
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["https://a.com", "https://b.com"]


def test_wildcard_in_env_uses_wildcard_no_credentials(monkeypatch):
    """Operator explicit '*' yazarsa: wildcard ama credentials=False."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    cfg = get_cors_config()
    assert cfg["allow_origins"] == ["*"]
    # CORS spec: '*' + credentials=True browser tarafindan reddedilir.
    # O yuzden '*' aktif iken credentials her zaman False.
    assert cfg["allow_credentials"] is False
