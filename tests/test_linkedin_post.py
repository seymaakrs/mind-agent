"""Tests for LinkedIn posting - LateClient and orchestrator tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from agents import RunContextWrapper

from src.infra.late_client import LateClient


async def _invoke_tool(tool, params: dict):
    """Helper: invoke a FunctionTool via on_invoke_tool."""
    ctx = RunContextWrapper(context=None)
    return await tool.on_invoke_tool(ctx, json.dumps(params))


def _mock_httpx(status_code=200, response_data=None):
    """Helper: create patched httpx client."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    if status_code >= 400:
        mock_response.text = response_data or "Error"
    else:
        mock_response.json.return_value = response_data or {
            "post": {
                "_id": "post_abc",
                "platforms": [
                    {
                        "platformPostId": "li_123",
                        "platformPostUrl": "https://linkedin.com/feed/update/li_123",
                        "status": "published",
                    }
                ],
            }
        }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    patcher = patch("httpx.AsyncClient", return_value=mock_client)
    return patcher, mock_client


# ---------------------------------------------------------------------------
# LateClient.post_linkedin tests
# ---------------------------------------------------------------------------


class TestLateClientPostLinkedIn:
    """Tests for LateClient.post_linkedin HTTP layer."""

    def setup_method(self):
        self.client = LateClient(api_key="sk_test_xxx", account_id="test_acc_id")

    @pytest.mark.asyncio
    async def test_text_only_post(self):
        """Text-only post - mediaItems olmadan."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            result = await self.client.post_linkedin(
                content="Just a text post on LinkedIn",
            )

        assert result["success"] is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["content"] == "Just a text post on LinkedIn"
        assert "mediaItems" not in payload
        assert payload["platforms"][0]["platform"] == "linkedin"
        assert payload["publishNow"] is True

    @pytest.mark.asyncio
    async def test_single_image_post(self):
        """Tek image post."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            result = await self.client.post_linkedin(
                content="Check this out",
                media_url="https://cdn.example.com/photo.jpg",
                media_type="image",
            )

        assert result["success"] is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["mediaItems"] == [{"type": "image", "url": "https://cdn.example.com/photo.jpg"}]

    @pytest.mark.asyncio
    async def test_video_post(self):
        """Tek video post."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            result = await self.client.post_linkedin(
                content="Watch this",
                media_url="https://cdn.example.com/video.mp4",
                media_type="video",
            )

        assert result["success"] is True
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["mediaItems"] == [{"type": "video", "url": "https://cdn.example.com/video.mp4"}]

    @pytest.mark.asyncio
    async def test_first_comment(self):
        """firstComment platformSpecificData icinde gitmeli."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(
                content="New guide published",
                first_comment="Read it here: https://example.com/guide",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        psd = payload["platforms"][0]["platformSpecificData"]
        assert psd["firstComment"] == "Read it here: https://example.com/guide"

    @pytest.mark.asyncio
    async def test_disable_link_preview(self):
        """disableLinkPreview platformSpecificData icinde gitmeli."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(
                content="Post with URL https://example.com",
                disable_link_preview=True,
            )

        payload = mock_client.post.call_args.kwargs["json"]
        psd = payload["platforms"][0]["platformSpecificData"]
        assert psd["disableLinkPreview"] is True

    @pytest.mark.asyncio
    async def test_organization_urn(self):
        """organizationUrn sirket sayfasi olarak paylasim."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(
                content="Company update",
                organization_urn="urn:li:organization:123456",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        psd = payload["platforms"][0]["platformSpecificData"]
        assert psd["organizationUrn"] == "urn:li:organization:123456"

    @pytest.mark.asyncio
    async def test_scheduled_post(self):
        """scheduledFor ile zamanlanmis post, publishNow false olmali."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(
                content="Scheduled post",
                scheduled_for="2026-03-01T10:00:00Z",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["publishNow"] is False
        assert payload["scheduledFor"] == "2026-03-01T10:00:00Z"

    @pytest.mark.asyncio
    async def test_no_platform_specific_data_when_no_options(self):
        """Hicbir opsiyonel parametre yoksa platformSpecificData olmamali."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(content="Simple post")

        payload = mock_client.post.call_args.kwargs["json"]
        assert "platformSpecificData" not in payload["platforms"][0]

    @pytest.mark.asyncio
    async def test_api_error(self):
        """API hata donerse error dondur."""
        patcher, _ = _mock_httpx(status_code=422, response_data="Duplicate content")
        with patcher:
            result = await self.client.post_linkedin(content="Duplicate")

        assert result["success"] is False
        assert result["status_code"] == 422

    @pytest.mark.asyncio
    async def test_all_options_combined(self):
        """Tum opsiyonel parametreler birlikte."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin(
                content="Full post",
                media_url="https://cdn.example.com/img.jpg",
                media_type="image",
                first_comment="Link: https://example.com",
                disable_link_preview=True,
                organization_urn="urn:li:organization:999",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["mediaItems"] == [{"type": "image", "url": "https://cdn.example.com/img.jpg"}]
        psd = payload["platforms"][0]["platformSpecificData"]
        assert psd["firstComment"] == "Link: https://example.com"
        assert psd["disableLinkPreview"] is True
        assert psd["organizationUrn"] == "urn:li:organization:999"


# ---------------------------------------------------------------------------
# LateClient.post_linkedin_carousel tests
# ---------------------------------------------------------------------------


class TestLateClientPostLinkedInCarousel:
    """Tests for LateClient.post_linkedin_carousel HTTP layer."""

    def setup_method(self):
        self.client = LateClient(api_key="sk_test_xxx", account_id="test_acc_id")

    @pytest.mark.asyncio
    async def test_multi_image_post(self):
        """Multi-image carousel post."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            result = await self.client.post_linkedin_carousel(
                media_items=[
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/3.jpg"},
                ],
                content="Three photos",
            )

        assert result["success"] is True
        assert result["item_count"] == 3
        payload = mock_client.post.call_args.kwargs["json"]
        assert len(payload["mediaItems"]) == 3
        assert payload["platforms"][0]["platform"] == "linkedin"

    @pytest.mark.asyncio
    async def test_carousel_with_all_options(self):
        """Carousel tum opsiyonel parametrelerle."""
        patcher, mock_client = _mock_httpx()
        with patcher:
            await self.client.post_linkedin_carousel(
                media_items=[
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                ],
                content="Org carousel",
                first_comment="Details: https://example.com",
                organization_urn="urn:li:organization:555",
                scheduled_for="2026-04-01T12:00:00Z",
            )

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["publishNow"] is False
        assert payload["scheduledFor"] == "2026-04-01T12:00:00Z"
        psd = payload["platforms"][0]["platformSpecificData"]
        assert psd["firstComment"] == "Details: https://example.com"
        assert psd["organizationUrn"] == "urn:li:organization:555"

    @pytest.mark.asyncio
    async def test_api_error(self):
        """API hata donerse."""
        patcher, _ = _mock_httpx(status_code=400, response_data="Bad request")
        with patcher:
            result = await self.client.post_linkedin_carousel(
                media_items=[
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
            )

        assert result["success"] is False
        assert result["status_code"] == 400


# ---------------------------------------------------------------------------
# post_on_linkedin tool tests
# ---------------------------------------------------------------------------


class TestPostOnLinkedInTool:
    """Tests for the post_on_linkedin orchestrator tool."""

    @pytest.mark.asyncio
    async def test_content_exceeds_3000_chars(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        result = await _invoke_tool(post_on_linkedin, {
            "content": "x" * 3001,
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "3000" in result["error"]

    @pytest.mark.asyncio
    async def test_no_content_and_no_media(self):
        """Content ve media ikisi de yoksa error."""
        from src.tools.orchestrator_tools import post_on_linkedin

        result = await _invoke_tool(post_on_linkedin, {
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "content" in result["error"].lower() or "media" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_media_url_without_media_type(self):
        """media_url varsa media_type da olmali."""
        from src.tools.orchestrator_tools import post_on_linkedin

        result = await _invoke_tool(post_on_linkedin, {
            "content": "Post",
            "media_url": "https://cdn.example.com/photo.jpg",
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "media_type" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_media_url(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        result = await _invoke_tool(post_on_linkedin, {
            "content": "Post",
            "media_url": "not-a-url",
            "media_type": "image",
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_business_not_found(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = None

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc):
            result = await _invoke_tool(post_on_linkedin, {
                "content": "Test",
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_linkedin_account_id(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"name": "Biz"}

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc):
            result = await _invoke_tool(post_on_linkedin, {
                "content": "Test",
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "linkedin" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_text_only_post(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin.return_value = {
            "success": True,
            "post_id": "post_1",
            "platform_post_id": "li_1",
            "platform_post_url": "https://linkedin.com/feed/update/li_1",
            "status": "published",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_on_linkedin, {
                "content": "Hello LinkedIn",
                "business_id": "biz_1",
            })

        assert result["success"] is True
        assert result["post_id"] == "li_1"
        mock_doc.get_document.assert_called_once_with("biz_1")
        mock_late.post_linkedin.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_image_post(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin.return_value = {
            "success": True, "post_id": "p1", "platform_post_id": "li_1",
            "platform_post_url": "https://linkedin.com/li_1", "status": "published",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_on_linkedin, {
                "content": "Photo post",
                "media_url": "https://cdn.example.com/photo.jpg",
                "media_type": "image",
                "business_id": "biz_1",
            })

        assert result["success"] is True
        call_kwargs = mock_late.post_linkedin.call_args.kwargs
        assert call_kwargs["media_url"] == "https://cdn.example.com/photo.jpg"
        assert call_kwargs["media_type"] == "image"

    @pytest.mark.asyncio
    async def test_optional_params_passed_through(self):
        """first_comment, disable_link_preview, organization_urn, scheduled_for gecmeli."""
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin.return_value = {
            "success": True, "post_id": "p1", "platform_post_id": "li_1",
            "platform_post_url": "https://linkedin.com/li_1", "status": "published",
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            await _invoke_tool(post_on_linkedin, {
                "content": "Test",
                "business_id": "biz_1",
                "first_comment": "Link here",
                "disable_link_preview": True,
                "organization_urn": "urn:li:organization:123",
                "scheduled_for": "2026-03-01T10:00:00Z",
            })

        kw = mock_late.post_linkedin.call_args.kwargs
        assert kw["first_comment"] == "Link here"
        assert kw["disable_link_preview"] is True
        assert kw["organization_urn"] == "urn:li:organization:123"
        assert kw["scheduled_for"] == "2026-03-01T10:00:00Z"

    @pytest.mark.asyncio
    async def test_late_api_failure_forwarded(self):
        from src.tools.orchestrator_tools import post_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin.return_value = {
            "success": False, "error": "Duplicate content", "status_code": 422,
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_on_linkedin, {
                "content": "Duplicate",
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "Duplicate" in result["error"]


# ---------------------------------------------------------------------------
# post_carousel_on_linkedin tool tests
# ---------------------------------------------------------------------------


class TestPostCarouselOnLinkedInTool:
    """Tests for the post_carousel_on_linkedin orchestrator tool."""

    @pytest.mark.asyncio
    async def test_too_few_media_items(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        result = await _invoke_tool(post_carousel_on_linkedin, {
            "media_items": [{"type": "image", "url": "https://a.com/1.jpg"}],
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "2" in result["error"]

    @pytest.mark.asyncio
    async def test_too_many_media_items(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        items = [{"type": "image", "url": f"https://a.com/{i}.jpg"} for i in range(21)]
        result = await _invoke_tool(post_carousel_on_linkedin, {
            "media_items": items,
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "20" in result["error"]

    @pytest.mark.asyncio
    async def test_content_exceeds_3000_chars(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        result = await _invoke_tool(post_carousel_on_linkedin, {
            "media_items": [
                {"type": "image", "url": "https://a.com/1.jpg"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "content": "x" * 3001,
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "3000" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_media_url(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        result = await _invoke_tool(post_carousel_on_linkedin, {
            "media_items": [
                {"type": "image", "url": "bad-url"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_url_in_media_item(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        result = await _invoke_tool(post_carousel_on_linkedin, {
            "media_items": [
                {"type": "image"},
                {"type": "image", "url": "https://a.com/2.jpg"},
            ],
            "business_id": "biz_1",
        })
        assert result["success"] is False
        assert "url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_business_not_found(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = None

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc):
            result = await _invoke_tool(post_carousel_on_linkedin, {
                "media_items": [
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_linkedin_account_id(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"name": "Biz"}

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc):
            result = await _invoke_tool(post_carousel_on_linkedin, {
                "media_items": [
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                "business_id": "biz_1",
            })

        assert result["success"] is False
        assert "linkedin" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_successful_carousel(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin_carousel.return_value = {
            "success": True,
            "post_id": "post_1",
            "platform_post_id": "li_car_1",
            "platform_post_url": "https://linkedin.com/feed/update/li_car_1",
            "status": "published",
            "item_count": 3,
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            result = await _invoke_tool(post_carousel_on_linkedin, {
                "media_items": [
                    {"type": "image", "url": "https://cdn.example.com/1.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/2.jpg"},
                    {"type": "image", "url": "https://cdn.example.com/3.jpg"},
                ],
                "content": "Three photos",
                "business_id": "biz_1",
            })

        assert result["success"] is True
        assert result["post_id"] == "li_car_1"
        assert result["content_type"] == "carousel"
        assert result["item_count"] == 3

    @pytest.mark.asyncio
    async def test_optional_params_passed_through(self):
        from src.tools.orchestrator_tools import post_carousel_on_linkedin

        mock_doc = MagicMock()
        mock_doc.get_document.return_value = {"linkedin_account_id": "acc_li_1"}

        mock_late = AsyncMock()
        mock_late.post_linkedin_carousel.return_value = {
            "success": True, "post_id": "p1", "platform_post_id": "li_1",
            "platform_post_url": "https://linkedin.com/li_1", "status": "ok", "item_count": 2,
        }

        with patch("src.tools.orchestrator_tools.get_document_client", return_value=mock_doc), \
             patch("src.tools.orchestrator_tools.get_late_client", return_value=mock_late):

            await _invoke_tool(post_carousel_on_linkedin, {
                "media_items": [
                    {"type": "image", "url": "https://a.com/1.jpg"},
                    {"type": "image", "url": "https://a.com/2.jpg"},
                ],
                "business_id": "biz_1",
                "first_comment": "Link here",
                "organization_urn": "urn:li:organization:999",
                "scheduled_for": "2026-04-01T12:00:00Z",
            })

        kw = mock_late.post_linkedin_carousel.call_args.kwargs
        assert kw["first_comment"] == "Link here"
        assert kw["organization_urn"] == "urn:li:organization:999"
        assert kw["scheduled_for"] == "2026-04-01T12:00:00Z"
