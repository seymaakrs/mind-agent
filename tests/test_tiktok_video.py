"""Tests for TikTok video posting - LateClient and orchestrator tool."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from agents import RunContextWrapper

from src.infra.late_client import LateClient


async def _invoke_tool(tool, params: dict):
    """Helper: invoke a FunctionTool with a dict of params via on_invoke_tool."""
    ctx = RunContextWrapper(context=None)
    return await tool.on_invoke_tool(ctx, json.dumps(params))


# ---------------------------------------------------------------------------
# LateClient.post_tiktok_video tests
# ---------------------------------------------------------------------------


class TestLateClientTikTokVideo:
    """Tests for LateClient.post_tiktok_video HTTP layer."""

    def setup_method(self):
        self.client = LateClient(api_key="sk_test_xxx", account_id="test_acc_id")

    def _mock_success_response(self, post_id="post_123", platform_post_id="tt_vid_456"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "post": {
                "_id": post_id,
                "platforms": [
                    {
                        "platformPostId": platform_post_id,
                        "platformPostUrl": f"https://tiktok.com/@user/video/{platform_post_id}",
                        "status": "published",
                    }
                ],
            }
        }
        return mock_response

    def _patch_httpx(self, mock_response):
        """Return context manager that patches httpx.AsyncClient."""
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        patcher = patch("httpx.AsyncClient", return_value=mock_client)
        return patcher, mock_client

    @pytest.mark.asyncio
    async def test_minimal_video_success(self):
        """Minimum zorunlu parametreler ile basarili video post."""
        patcher, mock_client = self._patch_httpx(self._mock_success_response())
        with patcher:
            result = await self.client.post_tiktok_video(
                video_url="https://cdn.example.com/video.mp4",
                content="New cooking tutorial #recipe",
                privacy_level="PUBLIC_TO_EVERYONE",
                allow_comment=True,
                allow_duet=True,
                allow_stitch=True,
            )

        assert result["success"] is True
        assert result["post_id"] == "post_123"
        assert result["platform_post_id"] == "tt_vid_456"
        assert result["type"] == "video"

        # Verify payload
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["content"] == "New cooking tutorial #recipe"
        assert payload["mediaItems"] == [{"type": "video", "url": "https://cdn.example.com/video.mp4"}]
        assert payload["platforms"][0]["platform"] == "tiktok"
        assert payload["publishNow"] is True

        ts = payload["tiktokSettings"]
        assert ts["privacy_level"] == "PUBLIC_TO_EVERYONE"
        assert ts["allow_comment"] is True
        assert ts["allow_duet"] is True
        assert ts["allow_stitch"] is True
        assert ts["content_preview_confirmed"] is True
        assert ts["express_consent_given"] is True

    @pytest.mark.asyncio
    async def test_full_optional_params(self):
        """Tum opsiyonel parametreler ile video post."""
        patcher, mock_client = self._patch_httpx(self._mock_success_response())
        with patcher:
            result = await self.client.post_tiktok_video(
                video_url="https://cdn.example.com/video.mp4",
                content="AI generated content",
                privacy_level="FOLLOWER_OF_CREATOR",
                allow_comment=False,
                allow_duet=False,
                allow_stitch=False,
                video_cover_timestamp_ms=3000,
                video_made_with_ai=True,
                draft=True,
                commercial_content_type="brand_content",
            )

        assert result["success"] is True

        ts = mock_client.post.call_args.kwargs["json"]["tiktokSettings"]
        assert ts["privacy_level"] == "FOLLOWER_OF_CREATOR"
        assert ts["allow_comment"] is False
        assert ts["allow_duet"] is False
        assert ts["allow_stitch"] is False
        assert ts["video_cover_timestamp_ms"] == 3000
        assert ts["video_made_with_ai"] is True
        assert ts["draft"] is True
        assert ts["commercialContentType"] == "brand_content"

    @pytest.mark.asyncio
    async def test_api_error_response(self):
        """API 4xx/5xx hata donerse error dondur."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: invalid video format"

        patcher, _ = self._patch_httpx(mock_response)
        with patcher:
            result = await self.client.post_tiktok_video(
                video_url="https://cdn.example.com/bad.avi",
                content="Test",
                privacy_level="PUBLIC_TO_EVERYONE",
                allow_comment=True,
                allow_duet=True,
                allow_stitch=True,
            )

        assert result["success"] is False
        assert result["status_code"] == 400
        assert "Bad Request" in result["error"]

    @pytest.mark.asyncio
    async def test_optional_fields_omitted_when_none(self):
        """Opsiyonel alanlar None ise payload'a eklenmemeli."""
        patcher, mock_client = self._patch_httpx(self._mock_success_response())
        with patcher:
            await self.client.post_tiktok_video(
                video_url="https://cdn.example.com/video.mp4",
                content="Test",
                privacy_level="PUBLIC_TO_EVERYONE",
                allow_comment=True,
                allow_duet=True,
                allow_stitch=True,
            )

        ts = mock_client.post.call_args.kwargs["json"]["tiktokSettings"]
        assert "video_cover_timestamp_ms" not in ts
        assert "video_made_with_ai" not in ts
        assert "draft" not in ts
        assert "commercialContentType" not in ts


# ---------------------------------------------------------------------------
# post_on_tiktok tool tests
# ---------------------------------------------------------------------------


class TestPostOnTikTokTool:
    """Tests for the orchestrator tool layer."""

    @pytest.mark.asyncio
    async def test_content_exceeds_2200_chars(self):
        """Content 2200 karakteri asarsa validation error."""
        from src.tools.orchestrator_tools import post_on_tiktok

        result = await _invoke_tool(post_on_tiktok, {
            "video_url": "https://cdn.example.com/video.mp4",
            "content": "x" * 2201,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "2200" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_video_url(self):
        """Video URL'si http ile baslamazsa validation error."""
        from src.tools.orchestrator_tools import post_on_tiktok

        result = await _invoke_tool(post_on_tiktok, {
            "video_url": "not-a-url",
            "content": "Test",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "URL" in result["error"] or "url" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_business_tiktok_account_id(self):
        """Business'ta tiktok_account_id yoksa error."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"name": "Biz"}

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client):
            result = await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/video.mp4",
                "content": "Test",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
            })

        assert result["success"] is False
        assert "tiktok" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_business_not_found(self):
        """Business bulunamazsa error."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = None

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client):
            result = await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/video.mp4",
                "content": "Test",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
            })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_post(self):
        """Basarili video post - Firebase lookup + LateClient cagirisi."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"tiktok_account_id": "acc_tt_999"}

        mock_late = AsyncMock()
        mock_late.post_tiktok_video.return_value = {
            "success": True,
            "post_id": "post_xyz",
            "platform_post_id": "tt_xyz",
            "platform_post_url": "https://tiktok.com/@user/video/tt_xyz",
            "status": "published",
            "type": "video",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/video.mp4",
                "content": "Cooking tutorial #recipe",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
                "allow_comment": True,
                "allow_duet": True,
                "allow_stitch": True,
            })

        assert result["success"] is True
        assert result["post_id"] == "tt_xyz"
        assert result["content_type"] == "video"

        mock_doc_client.get_document.assert_called_once_with("biz_123")
        mock_late.post_tiktok_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_allow_flags_are_true(self):
        """allow_comment, allow_duet, allow_stitch belirtilmezse True olarak gitmeli."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"tiktok_account_id": "acc_tt_1"}

        mock_late = AsyncMock()
        mock_late.post_tiktok_video.return_value = {
            "success": True,
            "post_id": "p1",
            "platform_post_id": "t1",
            "platform_post_url": "https://tiktok.com/v/t1",
            "status": "published",
            "type": "video",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/v.mp4",
                "content": "Test",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_1",
            })

        call_kwargs = mock_late.post_tiktok_video.call_args.kwargs
        assert call_kwargs["allow_comment"] is True
        assert call_kwargs["allow_duet"] is True
        assert call_kwargs["allow_stitch"] is True

    @pytest.mark.asyncio
    async def test_video_cover_timestamp_passed_through(self):
        """video_cover_timestamp_ms LateClient'a dogru gecmeli."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"tiktok_account_id": "acc_tt_1"}

        mock_late = AsyncMock()
        mock_late.post_tiktok_video.return_value = {
            "success": True, "post_id": "p1", "platform_post_id": "t1",
            "platform_post_url": "https://tiktok.com/v/t1", "status": "ok", "type": "video",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/v.mp4",
                "content": "Test",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_1",
                "video_cover_timestamp_ms": 5000,
            })

        assert mock_late.post_tiktok_video.call_args.kwargs["video_cover_timestamp_ms"] == 5000

    @pytest.mark.asyncio
    async def test_late_api_failure_forwarded(self):
        """Late API hata donerse tool da hata dondur."""
        from src.tools.orchestrator_tools import post_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"tiktok_account_id": "acc_tt_1"}

        mock_late = AsyncMock()
        mock_late.post_tiktok_video.return_value = {
            "success": False,
            "error": "Video too short",
            "status_code": 422,
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_on_tiktok, {
                "video_url": "https://cdn.example.com/short.mp4",
                "content": "Test",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "Video too short" in result["error"]
