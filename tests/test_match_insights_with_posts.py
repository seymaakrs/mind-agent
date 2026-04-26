"""
Tests for match_insights_with_posts utility.

This deterministic helper joins Late Analytics insights (which use Late's internal
postId) with Firestore-saved Instagram posts (which use Instagram's native media id)
via the URL field shared by both: platform_post_url ↔ permalink.

Why deterministic Python instead of LLM matching?
- URLs may differ in trailing slash, query params, http vs https.
- Token cost: an LLM matching 20+ insights is wasteful.
- Reliability: pure code is reproducible and unit-testable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


async def _invoke_tool(impl, params: dict):
    """Invoke the matching impl directly. The @function_tool wrapper is verified
    separately in test_function_tool_wrapper_registered."""
    return await impl(**params)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INSIGHT_A = {
    "id": "late_internal_a",
    "platform_post_url": "https://www.instagram.com/p/ABC123/",
    "metrics": {"reach": 100, "likes": 10},
}
INSIGHT_B = {
    "id": "late_internal_b",
    "platform_post_url": "https://www.instagram.com/p/DEF456/",
    "metrics": {"reach": 200, "likes": 20},
}
INSIGHT_NO_URL = {
    "id": "late_internal_c",
    "platform_post_url": None,
    "metrics": {"reach": 50, "likes": 5},
}

SAVED_A = {
    "instagram_media_id": "ig_a",
    "permalink": "https://www.instagram.com/p/ABC123/",
    "topic": "ürün tanıtımı",
    "theme": "ocak kampanyası",
}
SAVED_B = {
    "instagram_media_id": "ig_b",
    "permalink": "https://www.instagram.com/p/DEF456/",
    "topic": "behind the scenes",
    "theme": None,
}
SAVED_NO_PERMALINK = {
    "instagram_media_id": "ig_old",
    "permalink": None,
    "topic": "eski post",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMatchInsightsWithPosts:

    @pytest.mark.asyncio
    async def test_perfect_match(self):
        """Iki insight, iki kayıt, hepsi eşleşmeli."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A, SAVED_B]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_A, INSIGHT_B],
            })

        assert result["success"] is True
        assert len(result["matched"]) == 2
        assert result["unmatched"] == []
        assert result["match_rate"] == 1.0

        first = result["matched"][0]
        assert first["topic"] == "ürün tanıtımı"
        assert first["theme"] == "ocak kampanyası"
        # Insight metrics survive the merge.
        assert first["metrics"]["reach"] == 100

    @pytest.mark.asyncio
    async def test_partial_match(self):
        """Bir insight saved post yok → unmatched listesine düşmeli."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A]  # Only A saved

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_A, INSIGHT_B],
            })

        assert result["success"] is True
        assert len(result["matched"]) == 1
        assert len(result["unmatched"]) == 1
        assert result["matched"][0]["topic"] == "ürün tanıtımı"
        assert result["unmatched"][0]["id"] == "late_internal_b"
        assert result["match_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_url_normalization_trailing_slash(self):
        """URL'ler trailing slash farkıyla bile eşleşmeli."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        insight = {
            **INSIGHT_A,
            "platform_post_url": "https://www.instagram.com/p/ABC123",  # no slash
        }
        saved = {
            **SAVED_A,
            "permalink": "https://www.instagram.com/p/ABC123/",  # with slash
        }

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [saved]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [insight],
            })

        assert result["success"] is True
        assert len(result["matched"]) == 1
        assert result["matched"][0]["topic"] == "ürün tanıtımı"

    @pytest.mark.asyncio
    async def test_url_normalization_query_params(self):
        """URL'lerde query string varsa eşleştirme yine başarılı olmalı."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        insight = {
            **INSIGHT_A,
            "platform_post_url": "https://www.instagram.com/p/ABC123/?igshid=xyz",
        }

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [insight],
            })

        assert result["success"] is True
        assert len(result["matched"]) == 1

    @pytest.mark.asyncio
    async def test_insight_without_url_goes_unmatched(self):
        """platform_post_url=None olan insight unmatched olmalı."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_NO_URL],
            })

        assert result["success"] is True
        assert result["matched"] == []
        assert len(result["unmatched"]) == 1
        assert result["match_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_saved_post_without_permalink_is_skipped(self):
        """permalink=None saved postlar mapping dışında kalmalı (legacy migration)."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A, SAVED_NO_PERMALINK]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_A],
            })

        assert result["success"] is True
        assert len(result["matched"]) == 1
        assert result["matched"][0]["topic"] == "ürün tanıtımı"

    @pytest.mark.asyncio
    async def test_empty_insights_list(self):
        """Boş insights listesi → match_rate=0 ve crash yok."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [],
            })

        assert result["success"] is True
        assert result["matched"] == []
        assert result["unmatched"] == []
        assert result["match_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_firestore_error_is_handled(self):
        """Firestore exception fırlatırsa success=False döndür."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.side_effect = RuntimeError("firestore down")

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_A],
            })

        assert result["success"] is False
        assert "firestore down" in result["error"]

    @pytest.mark.asyncio
    async def test_matched_preserves_insight_metrics(self):
        """Matched objede orijinal insight metrikleri kaybolmamalı."""
        from src.tools.marketing.media_tracking import _match_insights_with_posts_impl as match_insights_with_posts

        mock_doc = MagicMock()
        mock_doc.list_documents.return_value = [SAVED_A]

        with patch(
            "src.tools.marketing.media_tracking.get_document_client",
            return_value=mock_doc,
        ):
            result = await _invoke_tool(match_insights_with_posts, {
                "business_id": "biz_1",
                "insights": [INSIGHT_A],
            })

        matched = result["matched"][0]
        # Insight fields preserved
        assert matched["id"] == "late_internal_a"
        assert matched["metrics"]["likes"] == 10
        # Saved post fields surfaced for analysis
        assert matched["topic"] == "ürün tanıtımı"
        assert matched["theme"] == "ocak kampanyası"
        # Saved post is also embedded under "saved_post" for full access
        assert matched["saved_post"]["instagram_media_id"] == "ig_a"


class TestFunctionToolRegistration:
    """Verify the @function_tool wrapper exposes the tool to the agent runtime."""

    def test_match_tool_is_a_function_tool(self):
        """The decorated symbol must be a FunctionTool the SDK can invoke."""
        from agents import FunctionTool
        from src.tools.marketing.media_tracking import match_insights_with_posts

        assert isinstance(match_insights_with_posts, FunctionTool)
        assert match_insights_with_posts.name == "match_insights_with_posts"

    def test_match_tool_is_in_marketing_tool_list(self):
        """get_marketing_tools() must include match_insights_with_posts so the
        marketing agent can actually call it."""
        from src.tools.marketing import get_marketing_tools, match_insights_with_posts

        tools = get_marketing_tools()
        assert match_insights_with_posts in tools
