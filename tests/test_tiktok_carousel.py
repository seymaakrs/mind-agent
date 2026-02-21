"""Tests for TikTok carousel posting - LateClient and orchestrator tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.infra.late_client import LateClient


# ---------------------------------------------------------------------------
# LateClient.post_tiktok_carousel tests
# ---------------------------------------------------------------------------


class TestLateClientTikTokCarousel:
    """Tests for LateClient.post_tiktok_carousel HTTP layer."""

    def setup_method(self):
        self.client = LateClient(api_key="sk_test_xxx", account_id="test_acc_id")

    @pytest.mark.asyncio
    async def test_minimal_carousel_success(self):
        """Minimum required params ile basarili carousel post."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "post": {
                "_id": "post_123",
                "platforms": [
                    {
                        "platformPostId": "tiktok_post_456",
                        "platformPostUrl": "https://tiktok.com/@user/photo/456",
                        "status": "published",
                    }
                ],
            }
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.client.post_tiktok_carousel(
                media_items=[
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                ],
                content="My carousel title",
                privacy_level="PUBLIC_TO_EVERYONE",
            )

        assert result["success"] is True
        assert result["post_id"] == "post_123"
        assert result["platform_post_id"] == "tiktok_post_456"
        assert result["type"] == "carousel"
        assert result["item_count"] == 2

        # Verify payload structure
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["content"] == "My carousel title"
        assert len(payload["mediaItems"]) == 2
        assert payload["platforms"][0]["platform"] == "tiktok"
        assert payload["tiktokSettings"]["media_type"] == "photo"
        assert payload["tiktokSettings"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
        assert payload["tiktokSettings"]["content_preview_confirmed"] is True
        assert payload["tiktokSettings"]["express_consent_given"] is True
        assert payload["publishNow"] is True

    @pytest.mark.asyncio
    async def test_full_params_carousel(self):
        """Tum opsiyonel parametreler ile carousel post."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "post": {
                "_id": "post_789",
                "platforms": [{"platformPostId": "tt_789", "platformPostUrl": "https://tiktok.com/789", "status": "published"}],
            }
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.client.post_tiktok_carousel(
                media_items=[
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/3.jpg"},
                ],
                content="Title here",
                privacy_level="MUTUAL_FOLLOW_FRIENDS",
                allow_comment=False,
                description="Full caption description up to 4000 chars",
                photo_cover_index=1,
                auto_add_music=True,
                video_made_with_ai=True,
                draft=False,
                commercial_content_type="BRANDED_CONTENT",
            )

        assert result["success"] is True

        # Verify all tiktokSettings fields
        payload = mock_client.post.call_args.kwargs["json"]
        ts = payload["tiktokSettings"]
        assert ts["privacy_level"] == "MUTUAL_FOLLOW_FRIENDS"
        assert ts["allow_comment"] is False
        assert ts["description"] == "Full caption description up to 4000 chars"
        assert ts["photo_cover_index"] == 1
        assert ts["auto_add_music"] is True
        assert ts["video_made_with_ai"] is True
        assert ts["draft"] is False
        assert ts["commercialContentType"] == "BRANDED_CONTENT"

    @pytest.mark.asyncio
    async def test_api_error_response(self):
        """API 4xx/5xx hata donerse error dondur."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Unprocessable Entity: invalid media_type"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await self.client.post_tiktok_carousel(
                media_items=[
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                ],
                content="Test",
                privacy_level="PUBLIC_TO_EVERYONE",
            )

        assert result["success"] is False
        assert result["status_code"] == 422
        assert "Unprocessable Entity" in result["error"]

    @pytest.mark.asyncio
    async def test_content_max_90_chars_not_enforced_by_client(self):
        """LateClient content uzunlugu kontrol etmez - bu tool katmaninda yapilir."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "post": {"_id": "p1", "platforms": [{"platformPostId": "t1", "status": "ok"}]}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # 100 char content - client should pass it through
            result = await self.client.post_tiktok_carousel(
                media_items=[
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                content="x" * 100,
                privacy_level="PUBLIC_TO_EVERYONE",
            )

        assert result["success"] is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert len(payload["content"]) == 100

    @pytest.mark.asyncio
    async def test_allow_comment_defaults_to_true(self):
        """allow_comment parametresi verilmezse True olarak gitmeli."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "post": {"_id": "p1", "platforms": [{"platformPostId": "t1", "status": "ok"}]}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await self.client.post_tiktok_carousel(
                media_items=[
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                content="Test",
                privacy_level="PUBLIC_TO_EVERYONE",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["tiktokSettings"]["allow_comment"] is True


# ---------------------------------------------------------------------------
# post_carousel_on_tiktok tool tests
# ---------------------------------------------------------------------------


async def _invoke_tool(tool, params: dict):
    """Helper: invoke a FunctionTool with a dict of params via on_invoke_tool."""
    import json
    from agents import RunContextWrapper

    ctx = RunContextWrapper(context=None)
    return await tool.on_invoke_tool(ctx, json.dumps(params))


class TestPostCarouselOnTikTokTool:
    """Tests for the orchestrator tool layer."""

    @pytest.mark.asyncio
    async def test_content_exceeds_90_chars(self):
        """Content 90 karakteri asarsa validation error dondur."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [
                {"type": "image", "url": "https://a.com/1.jpg"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "x" * 91,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "90" in result["error"]

    @pytest.mark.asyncio
    async def test_description_exceeds_4000_chars(self):
        """Description 4000 karakteri asarsa validation error."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [
                {"type": "image", "url": "https://a.com/1.jpg"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "OK title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
            "description": "x" * 4001,
        })
        assert result["success"] is False
        assert "4000" in result["error"]

    @pytest.mark.asyncio
    async def test_too_few_media_items(self):
        """1 media item ile carousel olusturulamaz."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [{"type": "image", "url": "https://a.com/1.jpg"}],
            "content": "Title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "2" in result["error"]

    @pytest.mark.asyncio
    async def test_too_many_media_items(self):
        """35'ten fazla media item olamaz."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        items = [{"type": "image", "url": f"https://a.com/{i}.jpg"} for i in range(36)]
        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": items,
            "content": "Title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "35" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_media_item_url(self):
        """Media item URL'si http ile baslamazsa validation error."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [
                {"type": "image", "url": "not-a-url"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "Title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "URL" in result["error"] or "url" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_url_in_media_item(self):
        """Media item'da url yoksa validation error."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [
                {"type": "image"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "Title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
        })
        assert result["success"] is False
        assert "url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_photo_cover_index_out_of_range(self):
        """photo_cover_index media_items sinirlari disindaysa error."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        result = await _invoke_tool(post_carousel_on_tiktok, {
            "media_items": [
                {"type": "image", "url": "https://a.com/1.jpg"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "Title",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "business_id": "biz_123",
            "photo_cover_index": 5,
        })
        assert result["success"] is False
        assert "cover" in result["error"].lower() or "index" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_post_fetches_tiktok_account_id(self):
        """Tool, business_id'den tiktok_account_id'yi Firebase'den almali."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"tiktok_account_id": "acc_tiktok_123"}

        mock_late = AsyncMock()
        mock_late.post_tiktok_carousel.return_value = {
            "success": True,
            "post_id": "post_abc",
            "platform_post_id": "tt_abc",
            "platform_post_url": "https://tiktok.com/@user/photo/abc",
            "status": "published",
            "type": "carousel",
            "item_count": 2,
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_carousel_on_tiktok, {
                "media_items": [
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                ],
                "content": "Test carousel",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
            })

        assert result["success"] is True
        assert result["post_id"] == "tt_abc"
        assert result["content_type"] == "carousel"

        # Verify Firebase lookup
        mock_doc_client.get_document.assert_called_once_with("biz_123")
        mock_late.post_tiktok_carousel.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_tiktok_account_id_in_business(self):
        """Business'ta tiktok_account_id yoksa error dondur."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = {"name": "Test Business"}

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client):
            result = await _invoke_tool(post_carousel_on_tiktok, {
                "media_items": [
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                "content": "Title",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
            })

        assert result["success"] is False
        assert "tiktok" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_business_not_found(self):
        """Business bulunamazsa error dondur."""
        from src.tools.orchestrator_tools import post_carousel_on_tiktok

        mock_doc_client = MagicMock()
        mock_doc_client.get_document.return_value = None

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc_client):
            result = await _invoke_tool(post_carousel_on_tiktok, {
                "media_items": [
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                "content": "Title",
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "business_id": "biz_123",
            })

        assert result["success"] is False
        assert "not found" in result["error"].lower() or "bulunamadı" in result["error"].lower()
