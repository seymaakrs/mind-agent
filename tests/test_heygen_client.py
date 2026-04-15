"""Tests for HeyGen Video Agent client and generate_video_heygen tool."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from agents import RunContextWrapper

from src.infra.heygen_client import HeyGenClient


async def _invoke_tool(tool, params: dict):
    """Helper: invoke a FunctionTool via on_invoke_tool."""
    ctx = RunContextWrapper(context=None)
    return await tool.on_invoke_tool(ctx, json.dumps(params))


# ---------------------------------------------------------------------------
# Client Initialization
# ---------------------------------------------------------------------------


class TestHeyGenClientInit:
    """HeyGenClient baslatma testleri."""

    @patch("src.infra.heygen_client.get_settings")
    def test_raises_without_api_key(self, mock_settings):
        """API key yoksa ValueError firlatmali."""
        mock_settings.return_value = MagicMock(heygen_api_key=None)
        with pytest.raises(ValueError, match="HEYGEN_API_KEY"):
            HeyGenClient()

    @patch("src.infra.heygen_client.get_settings")
    def test_initializes_with_api_key(self, mock_settings):
        """API key varsa baslatma basarili olmali."""
        mock_settings.return_value = MagicMock(heygen_api_key="test_key_123")
        client = HeyGenClient()
        assert client is not None

    @patch("src.infra.heygen_client.get_settings")
    def test_headers_contain_api_key(self, mock_settings):
        """X-Api-Key header'i API key'i icermeli."""
        mock_settings.return_value = MagicMock(heygen_api_key="my_secret_key")
        client = HeyGenClient()
        headers = client._get_headers()
        assert headers["X-Api-Key"] == "my_secret_key"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Asset Upload
# ---------------------------------------------------------------------------


class TestHeyGenAssetUpload:
    """Gorsel upload testleri."""

    @patch("src.infra.heygen_client.get_settings")
    @pytest.mark.asyncio
    async def test_upload_asset_returns_asset_id(self, mock_settings):
        """Upload basarili oldugunda asset_id donmeli."""
        mock_settings.return_value = MagicMock(heygen_api_key="test_key")
        client = HeyGenClient()

        # Mock: gorsel indirme ve upload
        mock_dl_response = MagicMock()
        mock_dl_response.status_code = 200
        mock_dl_response.content = b"fake_image_bytes"

        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200
        mock_upload_response.json.return_value = {
            "error": None,
            "data": {"id": "asset_abc123", "name": "test.jpg"},
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_dl_response)
        mock_client.post = AsyncMock(return_value=mock_upload_response)

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            asset_id = await client.upload_asset("https://example.com/image.jpg")

        assert asset_id == "asset_abc123"

    @patch("src.infra.heygen_client.get_settings")
    @pytest.mark.asyncio
    async def test_upload_detects_png_content_type(self, mock_settings):
        """PNG URL'den content-type image/png tespit edilmeli."""
        mock_settings.return_value = MagicMock(heygen_api_key="test_key")
        client = HeyGenClient()

        mock_dl_response = MagicMock()
        mock_dl_response.status_code = 200
        mock_dl_response.content = b"fake_png"

        mock_upload_response = MagicMock()
        mock_upload_response.status_code = 200
        mock_upload_response.json.return_value = {
            "error": None,
            "data": {"id": "asset_png_001"},
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_dl_response)
        mock_client.post = AsyncMock(return_value=mock_upload_response)

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            await client.upload_asset("https://cdn.example.com/photo.png")

        # PNG URL'de post Content-Type image/png olmali
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["Content-Type"] == "image/png"

    @patch("src.infra.heygen_client.get_settings")
    @pytest.mark.asyncio
    async def test_upload_fails_on_download_error(self, mock_settings):
        """Gorsel indirme basarisiz olursa ServiceError firlatmali."""
        from src.infra.errors import ServiceError

        mock_settings.return_value = MagicMock(heygen_api_key="test_key")
        client = HeyGenClient()

        mock_dl_response = MagicMock()
        mock_dl_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_dl_response)

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceError, match="Gorsel indirme hatasi"):
                await client.upload_asset("https://example.com/missing.jpg")


# ---------------------------------------------------------------------------
# Video Generation
# ---------------------------------------------------------------------------


class TestHeyGenVideoGeneration:
    """Video uretim testleri."""

    def _make_client(self):
        with patch("src.infra.heygen_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(heygen_api_key="test_key")
            return HeyGenClient()

    @pytest.mark.asyncio
    async def test_generate_video_text_only(self):
        """Prompt ile video uretimi video_id almali ve polling yapip bytes donmeli."""
        client = self._make_client()

        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.json.return_value = {
            "error": None,
            "data": {"video_id": "vid_test_001"},
        }

        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {
            "error": None,
            "data": {
                "status": "completed",
                "video_url": "https://heygen.com/video/test.mp4",
            },
        }

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.content = b"fake_video_bytes"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=generate_response)
        mock_client.get = AsyncMock(side_effect=[poll_response, download_response])

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            result = await client.generate_video(
                prompt="A professional corporate video",
                orientation="landscape",
            )

        assert result == b"fake_video_bytes"

        # Request body kontrolu
        post_call = mock_client.post.call_args
        body = post_call[1]["json"]
        assert body["prompt"] == "A professional corporate video"
        assert body["config"]["orientation"] == "landscape"
        assert "files" not in body  # image_url yoksa files eklenmemeli

    @pytest.mark.asyncio
    async def test_generate_video_with_duration(self):
        """duration_sec config'e eklenmeli."""
        client = self._make_client()

        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.json.return_value = {
            "error": None,
            "data": {"video_id": "vid_dur_001"},
        }

        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {
            "error": None,
            "data": {"status": "completed", "video_url": "https://heygen.com/v.mp4"},
        }

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.content = b"video"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=generate_response)
        mock_client.get = AsyncMock(side_effect=[poll_response, download_response])

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            await client.generate_video(
                prompt="Test video",
                orientation="portrait",
                duration_sec=15,
            )

        body = mock_client.post.call_args[1]["json"]
        assert body["config"]["duration_sec"] == 15
        assert body["config"]["orientation"] == "portrait"

    @pytest.mark.asyncio
    async def test_duration_minimum_enforced(self):
        """duration_sec minimum 5 olmali — 3 verilirse 5 olmali."""
        client = self._make_client()

        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.json.return_value = {
            "error": None,
            "data": {"video_id": "vid_min_001"},
        }

        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {
            "error": None,
            "data": {"status": "completed", "video_url": "https://heygen.com/v.mp4"},
        }

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.content = b"video"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=generate_response)
        mock_client.get = AsyncMock(side_effect=[poll_response, download_response])

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            await client.generate_video(prompt="Test", duration_sec=3)

        body = mock_client.post.call_args[1]["json"]
        assert body["config"]["duration_sec"] == 5  # min(5, 3) -> 5

    @pytest.mark.asyncio
    async def test_generate_video_with_image_uploads_asset(self):
        """image_url verildiginde asset upload yapilmali ve files eklenmeli."""
        client = self._make_client()

        upload_asset_mock = AsyncMock(return_value="asset_xyz_001")

        generate_response = MagicMock()
        generate_response.status_code = 200
        generate_response.json.return_value = {
            "error": None,
            "data": {"video_id": "vid_img_001"},
        }

        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {
            "error": None,
            "data": {"status": "completed", "video_url": "https://heygen.com/v.mp4"},
        }

        download_response = MagicMock()
        download_response.status_code = 200
        download_response.content = b"video_bytes"

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=generate_response)
        mock_http_client.get = AsyncMock(side_effect=[poll_response, download_response])

        with patch.object(client, "upload_asset", upload_asset_mock):
            with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_http_client):
                result = await client.generate_video(
                    prompt="Video from image",
                    image_url="https://example.com/ref.jpg",
                )

        upload_asset_mock.assert_called_once_with("https://example.com/ref.jpg")
        body = mock_http_client.post.call_args[1]["json"]
        assert body["files"] == [{"asset_id": "asset_xyz_001"}]
        assert result == b"video_bytes"


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------


class TestHeyGenPolling:
    """Video status polling testleri."""

    def _make_client(self):
        with patch("src.infra.heygen_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(heygen_api_key="test_key")
            return HeyGenClient()

    @pytest.mark.asyncio
    async def test_poll_waits_for_completed(self):
        """pending → processing → completed akisinda dogru URL donmeli."""
        client = self._make_client()

        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={
                "error": None,
                "data": {"status": "pending"},
            })),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "error": None,
                "data": {"status": "processing"},
            })),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "error": None,
                "data": {"status": "completed", "video_url": "https://cdn.heygen.com/final.mp4"},
            })),
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=responses)

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            with patch("src.infra.heygen_client.asyncio.sleep", new_callable=AsyncMock):
                url = await client._poll_video("vid_poll_001")

        assert url == "https://cdn.heygen.com/final.mp4"
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_poll_raises_on_failed(self):
        """Status failed oldugunda ServiceError firlatmali."""
        from src.infra.errors import ServiceError

        client = self._make_client()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "error": None,
                "data": {"status": "failed", "error": "Content policy violation"},
            }),
        ))

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceError, match="basarisiz"):
                await client._poll_video("vid_fail_001")

    @pytest.mark.asyncio
    async def test_poll_timeout(self):
        """MAX_POLL_ATTEMPTS asildiktan sonra TimeoutError firlatmali."""
        client = self._make_client()
        client.MAX_POLL_ATTEMPTS = 2  # Testi hizlandirmak icin

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={"error": None, "data": {"status": "processing"}}),
        ))

        with patch("src.infra.heygen_client.httpx.AsyncClient", return_value=mock_client):
            with patch("src.infra.heygen_client.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(TimeoutError):
                    await client._poll_video("vid_timeout_001")


# ---------------------------------------------------------------------------
# _check_response
# ---------------------------------------------------------------------------


class TestHeyGenCheckResponse:
    """HTTP response validasyon testleri."""

    def test_raises_on_non_200(self):
        """HTTP 4xx/5xx ServiceError firlatmali."""
        from src.infra.errors import ServiceError

        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized"

        with pytest.raises(ServiceError, match="401"):
            HeyGenClient._check_response(response)

    def test_raises_on_error_field(self):
        """Response body error field doluysa ServiceError firlatmali."""
        from src.infra.errors import ServiceError

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"error": "Invalid API key", "data": None}

        with pytest.raises(ServiceError, match="Invalid API key"):
            HeyGenClient._check_response(response)

    def test_passes_on_null_error(self):
        """error=null oldugunda exception firlatmamali."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"error": None, "data": {"video_id": "abc"}}

        # Hata firlatmamali
        HeyGenClient._check_response(response)


# ---------------------------------------------------------------------------
# generate_video_heygen Tool (DRY-RUN)
# ---------------------------------------------------------------------------


class TestGenerateVideoHeygenTool:
    """generate_video_heygen FunctionTool DRY-RUN testleri."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_expected_structure(self):
        """DRY-RUN modunda gercek API cagrisi yapilmamali."""
        from src.tools.video_tools import generate_video_heygen

        with patch("src.tools.video_tools.get_settings") as mock_settings, \
             patch("src.tools.video_tools.save_dry_run_log"):
            mock_settings.return_value = MagicMock(dry_run=True)

            result = await _invoke_tool(generate_video_heygen, {
                "prompt": "A modern office environment",
                "file_name": "test_heygen.mp4",
                "business_id": "biz_001",
                "orientation": "landscape",
            })

        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["dry_run"] is True
        assert "DRY-RUN" in result["message"]
        assert result["fileName"] == "test_heygen.mp4"

    @pytest.mark.asyncio
    async def test_dry_run_portrait_orientation(self):
        """DRY-RUN portrait orientation ile calisabilmeli."""
        from src.tools.video_tools import generate_video_heygen

        with patch("src.tools.video_tools.get_settings") as mock_settings, \
             patch("src.tools.video_tools.save_dry_run_log"):
            mock_settings.return_value = MagicMock(dry_run=True)

            result = await _invoke_tool(generate_video_heygen, {
                "prompt": "Instagram Reel content",
                "file_name": "reel.mp4",
                "orientation": "portrait",
                "duration_sec": 30,
            })

        assert result["success"] is True
        assert result["dry_run"] is True
