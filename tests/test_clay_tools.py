"""Clay tool tests — pure logic + discovery error path.

These cover:
- Lead scoring matrix (4 scenarios from Zernio spec)
- Outreach message generation (3 tones)
- CBO compliance check
- Discovery returns structured error when backend unconfigured
- Sector validation
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tools.sales.clay_tools import (
    FORBIDDEN_PHRASES,
    TARGET_SECTORS,
    _is_cbo_compliant,
)

# Import the tool's underlying coroutine via .__wrapped__ (function_tool decorator).
# Tools created via @function_tool expose original via tool.on_invoke_tool.
# To call the pure function in tests we use the underlying function — for our
# decorator approach (openai-agents `function_tool`), the original async fn is
# the decorated function itself.  We invoke it through the SDK's function tool
# machinery for end-to-end realism in the agent tests; here we test by direct
# call where possible.
#
# The simplest reliable path: import the module & call the wrapped fn via the
# `function_tool` returned object's underlying handler.  openai-agents stores
# the original under various attribute names depending on version; we use a
# small test helper to call them.
from src.tools.sales import clay_tools as ct


async def _call_tool(tool, **kwargs):
    """Invoke a function_tool-decorated tool by going through its internal callable."""
    # Strategy: openai-agents' FunctionTool exposes ``on_invoke_tool(ctx, args_json)``
    # but ALSO retains the original in ``params_json_schema``-ed wrapper. Easiest is
    # to reach for the underlying coroutine via attribute fallbacks.
    for attr in ("__wrapped__", "_func", "func", "fn"):
        fn = getattr(tool, attr, None)
        if callable(fn):
            return await fn(**kwargs)
    # Fallback: invoke via on_invoke_tool with serialised kwargs.
    import json

    return await tool.on_invoke_tool(None, json.dumps(kwargs))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CBO compliance helper
# ---------------------------------------------------------------------------


class TestCBOCompliance:
    def test_clean_message_passes(self) -> None:
        ok, hits = _is_cbo_compliant("Merhaba, değer katmak isterim. Birlikte büyüyelim.")
        assert ok is True
        assert hits == []

    def test_son_sans_blocked(self) -> None:
        ok, hits = _is_cbo_compliant("Son şans! Hemen al!")
        assert ok is False
        assert "son şans" in hits
        assert "hemen al" in hits

    def test_case_insensitive(self) -> None:
        ok, hits = _is_cbo_compliant("KAÇIRMA bu fırsatı!")
        assert ok is False
        assert "kaçırma" in hits


# ---------------------------------------------------------------------------
# Scoring matrix (Zernio agent-spec rules)
# ---------------------------------------------------------------------------


class TestScoreBusinessPresence:
    @pytest.mark.asyncio
    async def test_no_website_no_instagram_scores_10(self) -> None:
        out = await _call_tool(
            ct.score_business_presence,
            business_name="Test Hotel",
            has_website=False,
            has_instagram=False,
        )
        assert out["success"] is True
        assert out["score"] == 10
        assert "website" in out["weak_areas"]
        assert "instagram" in out["weak_areas"]

    @pytest.mark.asyncio
    async def test_only_website_missing_scores_7(self) -> None:
        out = await _call_tool(
            ct.score_business_presence,
            business_name="Test",
            has_website=False,
            has_instagram=True,
            instagram_follower_count=2000,
        )
        assert out["score"] == 7
        assert out["weak_areas"] == ["website"]

    @pytest.mark.asyncio
    async def test_weak_instagram_followers_treated_as_weak(self) -> None:
        out = await _call_tool(
            ct.score_business_presence,
            business_name="Test",
            has_website=True,
            has_instagram=True,
            instagram_follower_count=200,  # below 500 threshold
        )
        assert out["score"] == 7  # only IG weak
        assert "instagram" in out["weak_areas"]

    @pytest.mark.asyncio
    async def test_strong_presence_low_reviews_scores_5(self) -> None:
        out = await _call_tool(
            ct.score_business_presence,
            business_name="Test",
            has_website=True,
            has_instagram=True,
            instagram_follower_count=10_000,
            google_rating=4.5,
            google_review_count=3,  # too few reviews
        )
        assert out["score"] == 5

    @pytest.mark.asyncio
    async def test_everything_strong_scores_3(self) -> None:
        out = await _call_tool(
            ct.score_business_presence,
            business_name="Test",
            has_website=True,
            has_instagram=True,
            instagram_follower_count=20_000,
            google_rating=4.8,
            google_review_count=200,
        )
        assert out["score"] == 3


# ---------------------------------------------------------------------------
# Outreach message generation
# ---------------------------------------------------------------------------


class TestGenerateOutreachMessage:
    @pytest.mark.asyncio
    async def test_value_tone_default(self) -> None:
        out = await _call_tool(
            ct.generate_outreach_message,
            business_name="Slowdays Hotel",
            sector="otel",
            weak_areas=["website", "instagram"],
            location="Bodrum",
        )
        assert out["success"] is True
        assert out["tone"] == "value"
        assert "Slowdays Hotel" in out["message"]
        assert "Bodrum" in out["message"]
        assert out["cbo_compliant"] is True
        assert out["violations"] == []

    @pytest.mark.asyncio
    async def test_soft_tone(self) -> None:
        out = await _call_tool(
            ct.generate_outreach_message,
            business_name="Ali Cafe",
            sector="cafe",
            weak_areas=["instagram"],
            tone="soft",
        )
        assert out["tone"] == "soft"
        assert "Ali Cafe" in out["message"]
        assert out["cbo_compliant"] is True

    @pytest.mark.asyncio
    async def test_direct_tone_still_compliant(self) -> None:
        out = await _call_tool(
            ct.generate_outreach_message,
            business_name="Veli Restaurant",
            sector="restoran",
            weak_areas=[],
            tone="direct",
        )
        assert out["tone"] == "direct"
        # No forbidden phrases ever — even in 'direct' tone
        assert out["cbo_compliant"] is True

    @pytest.mark.asyncio
    async def test_no_forbidden_phrases_in_any_template(self) -> None:
        for tone in ("value", "soft", "direct"):
            out = await _call_tool(
                ct.generate_outreach_message,
                business_name="X",
                sector="otel",
                weak_areas=[],
                tone=tone,  # type: ignore[arg-type]
            )
            for phrase in FORBIDDEN_PHRASES:
                assert phrase not in out["message"].lower(), (
                    f"Forbidden phrase '{phrase}' found in {tone} template"
                )


# ---------------------------------------------------------------------------
# Discovery — error paths
# ---------------------------------------------------------------------------


class TestDiscoverLocalBusinesses:
    @pytest.mark.asyncio
    async def test_unknown_sector_rejected(self) -> None:
        out = await _call_tool(
            ct.discover_local_businesses,
            location="Bodrum",
            sector="kuyumcu",  # not in TARGET_SECTORS
            limit=5,
        )
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_target_sectors_accepted_one_per_call(self) -> None:
        # Just confirm at least one target sector is recognised end-to-end.
        # We patch the backend so we don't need real env config.
        async def _fake_backend(loc: str, sec: str, lim: int):
            return [{"name": f"Demo {sec}", "sector": sec, "location": loc}]

        with patch.object(ct, "_call_clay_backend", _fake_backend):
            out = await _call_tool(
                ct.discover_local_businesses,
                location="Bodrum",
                sector="otel",
                limit=1,
            )
            assert out["success"] is True
            assert out["count"] == 1
            assert out["businesses"][0]["sector"] == "otel"

    @pytest.mark.asyncio
    async def test_unconfigured_backend_returns_not_found(self) -> None:
        # Wipe env so backend URL is missing.
        with patch.dict(os.environ, {"CLAY_BACKEND_URL": "", "CLAY_BACKEND_TOKEN": ""}, clear=False):
            out = await _call_tool(
                ct.discover_local_businesses,
                location="Bodrum",
                sector="otel",
                limit=5,
            )
            assert out["success"] is False
            assert out["error_code"] == "NOT_FOUND"
            assert "configured" in out["error"].lower()

    @pytest.mark.asyncio
    async def test_backend_http_error_classified(self) -> None:
        async def _err_backend(loc: str, sec: str, lim: int):
            from src.infra.errors import ServiceError

            raise ServiceError(
                "rate limited", status_code=429, service="clay"
            )

        with patch.object(ct, "_call_clay_backend", _err_backend):
            out = await _call_tool(
                ct.discover_local_businesses,
                location="Bodrum",
                sector="otel",
                limit=5,
            )
            assert out["success"] is False
            assert out["error_code"] == "RATE_LIMIT"
            assert out["retryable"] is True
