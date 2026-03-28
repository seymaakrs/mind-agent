"""Tests for Kling AI client and generate_video_kling tool."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import json

import httpx
import jwt
import pytest
from agents import RunContextWrapper

from src.infra.kling_client import KlingVideoClient


async def _invoke_tool(tool, params: dict):
    """Helper: invoke a FunctionTool via on_invoke_tool."""
    ctx = RunContextWrapper(context=None)
    return await tool.on_invoke_tool(ctx, json.dumps(params))


# ---------------------------------------------------------------------------
# JWT Token Generation
# ---------------------------------------------------------------------------


class TestKlingJWT:
    """JWT token uretimi testleri."""

    @patch("src.infra.kling_client.get_model_settings")
    @patch("src.infra.kling_client.get_settings")
    def test_jwt_generates_valid_token(self, mock_settings, mock_model_settings):
        """JWT token HS256 ile imzalanmali ve dogru claims icermeli."""
        mock_settings.return_value = MagicMock(
            kling_access_key="test_ak_123",
            kling_secret_key="test_sk_456",
        )
        mock_model_settings.return_value = MagicMock(kling_video_model="kling-v3")

        client = KlingVideoClient()
        token = client._generate_jwt()

        # Decode and verify
        decoded = jwt.decode(token, "test_sk_456", algorithms=["HS256"])
        assert decoded["iss"] == "test_ak_123"
        assert "exp" in decoded
        assert "nbf" in decoded
        # Token should expire in ~30 minutes
        assert decoded["exp"] - decoded["nbf"] <= 1810  # 1800 + 5s tolerance + 5s nbf offset

    @patch("src.infra.kling_client.get_model_settings")
    @patch("src.infra.kling_client.get_settings")
    def test_jwt_has_correct_header(self, mock_settings, mock_model_settings):
        """JWT header alg=HS256, typ=JWT olmali."""
        mock_settings.return_value = MagicMock(
            kling_access_key="ak",
            kling_secret_key="sk",
        )
        mock_model_settings.return_value = MagicMock(kling_video_model="kling-v3")

        client = KlingVideoClient()
        token = client._generate_jwt()

        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"
        assert header["typ"] == "JWT"

    @patch("src.infra.kling_client.get_settings")
    def test_missing_keys_raises_error(self, mock_settings):
        """KLING_ACCESS_KEY veya SECRET_KEY yoksa ValueError firlatmali."""
        mock_settings.return_value = MagicMock(
            kling_access_key=None,
            kling_secret_key=None,
        )

        with pytest.raises(ValueError, match="KLING_ACCESS_KEY"):
            KlingVideoClient()


# ---------------------------------------------------------------------------
# Request Formatting
# ---------------------------------------------------------------------------


class TestKlingRequests:
    """API request format testleri."""

    @patch("src.infra.kling_client.get_model_settings")
    @patch("src.infra.kling_client.get_settings")
    def _make_client(self, mock_settings, mock_model_settings):
        mock_settings.return_value = MagicMock(
            kling_access_key="ak",
            kling_secret_key="sk",
        )
        mock_model_settings.return_value = MagicMock(kling_video_model="kling-v3")
        return KlingVideoClient()

    def test_headers_contain_bearer_jwt(self):
        """Headers Authorization: Bearer <jwt> formatinda olmali."""
        client = self._make_client()
        headers = client._get_headers()
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Content-Type"] == "application/json"

    def test_model_from_settings(self):
        """Model Firebase settings'den okunmali."""
        client = self._make_client()
        assert client._model == "kling-v3"


# ---------------------------------------------------------------------------
# Polling Logic
# ---------------------------------------------------------------------------


class TestKlingPolling:
    """Task polling testleri."""

    @patch("src.infra.kling_client.get_model_settings")
    @patch("src.infra.kling_client.get_settings")
    def _make_client(self, mock_settings, mock_model_settings):
        mock_settings.return_value = MagicMock(
            kling_access_key="ak",
            kling_secret_key="sk",
        )
        mock_model_settings.return_value = MagicMock(kling_video_model="kling-v3")
        return KlingVideoClient()

    @pytest.mark.asyncio
    async def test_poll_succeed_returns_url(self):
        """Status 'succeed' olunca video URL donmeli."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "task_id": "task_123",
                "task_status": "succeed",
                "output": {
                    "works": [
                        {"url": "https://cdn.klingai.com/video123.mp4", "width": 1080, "height": 1920}
                    ]
                },
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            url = await client._poll_task("task_123")
            assert url == "https://cdn.klingai.com/video123.mp4"

    @pytest.mark.asyncio
    async def test_poll_failed_raises_error(self):
        """Status 'failed' olunca RuntimeError firlatmali."""
        client = self._make_client()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "task_id": "task_123",
                "task_status": "failed",
                "task_status_msg": "Content policy violation",
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="basarisiz"):
                await client._poll_task("task_123")

    @pytest.mark.asyncio
    async def test_poll_timeout_raises_error(self):
        """Max poll sayisi asildiysa TimeoutError firlatmali."""
        client = self._make_client()
        client.MAX_POLL_ATTEMPTS = 2
        client.POLL_INTERVAL = 0  # Test hizi icin

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "task_id": "task_123",
                "task_status": "processing",
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with pytest.raises(TimeoutError, match="zaman asimi"):
                await client._poll_task("task_123")


# ---------------------------------------------------------------------------
# Response Validation
# ---------------------------------------------------------------------------


class TestKlingResponseCheck:
    """_check_response testleri."""

    def test_http_error_raises(self):
        """HTTP 4xx/5xx RuntimeError firlatmali."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.text = "Unauthorized"

        with pytest.raises(RuntimeError, match="401"):
            KlingVideoClient._check_response(response)

    def test_api_error_code_raises(self):
        """HTTP 200 ama code != 0 ise RuntimeError firlatmali."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {
            "code": 1001,
            "message": "Invalid parameter",
        }

        with pytest.raises(RuntimeError, match="Invalid parameter"):
            KlingVideoClient._check_response(response)

    def test_success_response_passes(self):
        """HTTP 200 + code 0 → hata yok."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"code": 0, "message": "success"}

        # Should not raise
        KlingVideoClient._check_response(response)


# ---------------------------------------------------------------------------
# generate_video_kling Tool (DRY-RUN)
# ---------------------------------------------------------------------------


class TestGenerateVideoKlingTool:
    """generate_video_kling tool testi (DRY-RUN mode)."""

    @pytest.mark.asyncio
    @patch("src.tools.video_tools.save_dry_run_log")
    @patch("src.tools.video_tools.get_settings")
    async def test_dry_run_returns_success(self, mock_settings, mock_dry_log):
        """DRY-RUN modda API cagirmadan basarili sonuc donmeli."""
        mock_settings.return_value = MagicMock(dry_run=True)

        from src.tools.video_tools import generate_video_kling

        result = await _invoke_tool(generate_video_kling, {
            "prompt": "A sunset over the ocean",
            "file_name": "sunset.mp4",
            "business_id": "biz123",
        })

        assert result["success"] is True
        assert "DRY-RUN" in result["message"]
        assert result["fileName"] == "sunset.mp4"
        assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# Config Integration
# ---------------------------------------------------------------------------


class TestKlingConfig:
    """Config entegrasyonu testleri."""

    @patch("src.app.config._load_model_settings_from_firebase")
    def test_kling_model_in_settings(self, mock_firebase):
        """ModelSettings kling_video_model icermeli."""
        from src.app.config import ModelSettings, clear_model_settings_cache, get_model_settings

        clear_model_settings_cache()
        mock_firebase.return_value = {"klingVideoModel": "kling-v3-custom"}

        settings = get_model_settings()
        assert settings.kling_video_model == "kling-v3-custom"

        # Cleanup
        clear_model_settings_cache()

    def test_kling_model_default(self):
        """Default kling model 'kling-v3' olmali."""
        from src.app.config import ModelSettings

        settings = ModelSettings()
        assert settings.kling_video_model == "kling-v3"

    def test_settings_has_kling_fields(self):
        """Settings class'inda kling_access_key ve kling_secret_key olmali."""
        from src.app.config import Settings

        # Field'lar mevcut olmali
        field_names = set(Settings.model_fields.keys())
        assert "kling_access_key" in field_names
        assert "kling_secret_key" in field_names
