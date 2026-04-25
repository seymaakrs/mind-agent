"""
NocoDBClient testleri.

Davranis:
- Bir HTTP client (NocoDB REST API v2 ile konusur).
- Whitelist'li tablolar: leads, pipeline, etkilesimler.
- Whitelist'li yazma kolonlari (sadece leads icin): notlar, seo_raporu_url,
  son_analiz_tarihi.
- Yazma whitelist disi → ValueError (programlama hatasi).
- Network/auth hatalari → ServiceError dict (mind-agent geneli pattern).
- Tolerant reader: cevap kolonu eksikse null/{} doner.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infra.nocodb_client import (
    NOCODB_WRITABLE_COLUMNS,
    NocoDBClient,
    NocoDBConfig,
)


@pytest.fixture
def config() -> NocoDBConfig:
    return NocoDBConfig(
        base_url="http://nocodb.test",
        api_token="fake-token",
        base_id="p_test",
        table_leads="tbl_leads",
        table_pipeline="tbl_pipeline",
        table_etkilesimler="tbl_etkilesimler",
    )


@pytest.fixture
def client(config) -> NocoDBClient:
    return NocoDBClient(config)


# ---------------------------------------------------------------------------
# Configuration / initialization
# ---------------------------------------------------------------------------


def test_config_required_fields():
    """Eksik konfig ile NocoDBConfig olusturulamaz."""
    with pytest.raises(ValueError):
        NocoDBConfig.from_settings(
            base_url=None, api_token=None, base_id=None,
            table_leads=None, table_pipeline=None, table_etkilesimler=None,
        )


def test_config_from_settings_full():
    """Tum env'ler dolu → NocoDBConfig olusur."""
    cfg = NocoDBConfig.from_settings(
        base_url="http://x", api_token="t", base_id="b",
        table_leads="l", table_pipeline="p", table_etkilesimler="e",
    )
    assert cfg.base_url == "http://x"
    assert cfg.api_token == "t"


# ---------------------------------------------------------------------------
# list_leads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_leads_returns_records(client):
    """Basarili cevap → records listesi."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "list": [
            {"Id": 1, "ad_soyad": "Ahmet", "asama": "Sicak"},
            {"Id": 2, "ad_soyad": "Ayse", "asama": "Yeni"},
        ],
        "pageInfo": {"totalRows": 2, "page": 1, "pageSize": 25},
    }

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        result = await client.list_leads(limit=10)

    assert result["success"] is True
    assert len(result["records"]) == 2
    assert result["records"][0]["ad_soyad"] == "Ahmet"


@pytest.mark.asyncio
async def test_list_leads_empty_is_graceful(client):
    """Bos cevap hata degil — bos liste ve success=True."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"list": [], "pageInfo": {"totalRows": 0}}

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        result = await client.list_leads()

    assert result["success"] is True
    assert result["records"] == []


@pytest.mark.asyncio
async def test_list_leads_uses_xc_token_header(client):
    """Istek 'xc-token' header'i ile gider (NocoDB standardi)."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"list": [], "pageInfo": {"totalRows": 0}}

    mock_get = AsyncMock(return_value=fake_response)
    with patch("httpx.AsyncClient.get", new=mock_get):
        await client.list_leads()

    call_kwargs = mock_get.call_args.kwargs
    headers = call_kwargs.get("headers", {})
    assert headers.get("xc-token") == "fake-token"


# ---------------------------------------------------------------------------
# get_lead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_lead_returns_single(client):
    """ID bazli arama → tek kayit doner."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"Id": 42, "ad_soyad": "Test"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        result = await client.get_lead(42)

    assert result["success"] is True
    assert result["record"]["Id"] == 42


@pytest.mark.asyncio
async def test_get_lead_404_returns_not_found(client):
    """Lead bulunamazsa NOT_FOUND error_code doner."""
    fake_response = MagicMock()
    fake_response.status_code = 404
    fake_response.json.return_value = {"msg": "Not found"}
    fake_response.text = "Not found"

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        result = await client.get_lead(9999)

    assert result["success"] is False
    assert result["error_code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# update_lead — whitelist enforcement
# ---------------------------------------------------------------------------


def test_writable_columns_whitelist_includes_expected():
    """Whitelist sadece sozlesmedeki kolonlari icerir (Bolum 2)."""
    assert "notlar" in NOCODB_WRITABLE_COLUMNS
    assert "seo_raporu_url" in NOCODB_WRITABLE_COLUMNS
    assert "son_analiz_tarihi" in NOCODB_WRITABLE_COLUMNS
    # Asla yazilmamasi gereken kolonlar:
    assert "lead_skoru" not in NOCODB_WRITABLE_COLUMNS
    assert "asama" not in NOCODB_WRITABLE_COLUMNS
    assert "kaynak" not in NOCODB_WRITABLE_COLUMNS


@pytest.mark.asyncio
async def test_update_lead_rejects_non_whitelist_column(client):
    """Whitelist disi kolon → ValueError, HTTP cagrisi yapilmaz."""
    mock_patch = AsyncMock()
    with patch("httpx.AsyncClient.patch", new=mock_patch):
        with pytest.raises(ValueError, match="not writable"):
            await client.update_lead(1, {"asama": "Sicak"})

    # HTTP cagrisi YAPILMAMALI
    mock_patch.assert_not_called()


@pytest.mark.asyncio
async def test_update_lead_accepts_whitelist_column(client):
    """Whitelist'teki kolon → HTTP cagrisi yapilir."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"Id": 1, "notlar": "yeni not"}

    with patch("httpx.AsyncClient.patch", new=AsyncMock(return_value=fake_response)):
        result = await client.update_lead(1, {"notlar": "yeni not"})

    assert result["success"] is True


# ---------------------------------------------------------------------------
# Hata davranisi (ServiceError pattern)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_returns_service_error(client):
    """Network hatasi → NETWORK_ERROR + retryable=True."""
    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        result = await client.list_leads()

    assert result["success"] is False
    assert result["error_code"] == "NETWORK_ERROR"
    assert result["retryable"] is True


@pytest.mark.asyncio
async def test_auth_error_returns_service_error(client):
    """401 → AUTH_ERROR, retryable=False."""
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.json.return_value = {"msg": "Unauthorized"}
    fake_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        result = await client.list_leads()

    assert result["success"] is False
    assert result["error_code"] == "AUTH_ERROR"
    assert result["retryable"] is False
