"""Tests for ShadowPublisher and factory shadow-mode wiring (Faz 3)."""
from __future__ import annotations

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


def _publisher_stub(backend_name: str, **methods):
    """Return a MagicMock with backend + account_id attrs and given AsyncMocks."""
    m = MagicMock()
    m.backend = backend_name
    m.account_id = "acc_x"
    for name, value in methods.items():
        setattr(m, name, value)
    return m


# ---------------------------------------------------------------------------
# ShadowPublisher behavior
# ---------------------------------------------------------------------------


class TestShadowPublisher:
    @pytest.mark.asyncio
    async def test_returns_primary_result_and_calls_both(self):
        from src.infra.publisher import PublishResult, ShadowPublisher

        primary_result = PublishResult(success=True, post_id="p_pri", status="published")
        shadow_result = PublishResult(success=True, post_id="p_sha", status="published")

        primary = _publisher_stub("late", instagram_post=AsyncMock(return_value=primary_result))
        shadow = _publisher_stub("zernio", instagram_post=AsyncMock(return_value=shadow_result))

        sp = ShadowPublisher(primary=primary, shadow=shadow)
        out = await sp.instagram_post(
            media_url="u", caption="c", media_type="image"
        )

        assert out is primary_result
        primary.instagram_post.assert_awaited_once()
        shadow.instagram_post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shadow_exception_is_swallowed(self, caplog):
        from src.infra.publisher import PublishResult, ShadowPublisher

        primary_result = PublishResult(success=True, post_id="p_pri", status="published")
        primary = _publisher_stub(
            "late", instagram_post=AsyncMock(return_value=primary_result)
        )
        shadow = _publisher_stub(
            "zernio", instagram_post=AsyncMock(side_effect=RuntimeError("boom"))
        )

        sp = ShadowPublisher(primary=primary, shadow=shadow)
        with caplog.at_level(logging.WARNING, logger="publisher.shadow"):
            out = await sp.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

        assert out is primary_result
        assert any("shadow=zernio/EXC" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_primary_exception_propagates(self):
        from src.infra.publisher import ShadowPublisher

        primary = _publisher_stub(
            "late", instagram_post=AsyncMock(side_effect=ValueError("primary broke"))
        )
        shadow = _publisher_stub("zernio", instagram_post=AsyncMock(return_value=None))

        sp = ShadowPublisher(primary=primary, shadow=shadow)
        with pytest.raises(ValueError, match="primary broke"):
            await sp.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

    @pytest.mark.asyncio
    async def test_diff_logged_when_results_disagree(self, caplog):
        from src.infra.publisher import PublishResult, ShadowPublisher

        primary_result = PublishResult(success=True, status="published", platform_post_id="ig_1")
        shadow_result = PublishResult(success=False, status="failed", error="x", status_code=500)

        primary = _publisher_stub(
            "late", instagram_post=AsyncMock(return_value=primary_result)
        )
        shadow = _publisher_stub(
            "zernio", instagram_post=AsyncMock(return_value=shadow_result)
        )

        sp = ShadowPublisher(primary=primary, shadow=shadow)
        with caplog.at_level(logging.WARNING, logger="publisher.shadow"):
            await sp.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

        msgs = " ".join(rec.message for rec in caplog.records)
        assert "diff=" in msgs
        assert "success" in msgs  # success field differs
        assert "status" in msgs

    @pytest.mark.asyncio
    async def test_parity_logged_at_info_when_equal(self, caplog):
        from src.infra.publisher import PublishResult, ShadowPublisher

        same = PublishResult(success=True, status="published", platform_post_id="ig_1")
        same2 = PublishResult(success=True, status="published", platform_post_id="ig_2")
        # different ID is OK — diff compares categorical fields only

        primary = _publisher_stub("late", instagram_post=AsyncMock(return_value=same))
        shadow = _publisher_stub("zernio", instagram_post=AsyncMock(return_value=same2))

        sp = ShadowPublisher(primary=primary, shadow=shadow)
        with caplog.at_level(logging.INFO, logger="publisher.shadow"):
            await sp.instagram_post(
                media_url="u", caption="c", media_type="image"
            )

        msgs = " ".join(rec.message for rec in caplog.records)
        assert "parity=ok" in msgs


# ---------------------------------------------------------------------------
# Factory shadow resolution
# ---------------------------------------------------------------------------


class TestShadowFactory:
    def test_shadow_env_wraps_in_shadow_publisher(self, monkeypatch):
        from src.infra.publisher import ShadowPublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_SHADOW", "true")
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test")
        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x")
        assert isinstance(pub, ShadowPublisher)
        assert pub.backend.startswith("shadow(")

    def test_explicit_shadow_false_overrides_env(self, monkeypatch):
        from src.infra.publisher import LatePublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_SHADOW", "true")
        with patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x", shadow=False)
        assert isinstance(pub, LatePublisher)

    def test_shadow_swallows_secondary_setup_error(self, monkeypatch):
        """If we can't build the shadow backend, fall back to the primary."""
        from src.infra.publisher import LatePublisher, get_publisher

        monkeypatch.setenv("PUBLISHER_SHADOW", "true")
        with patch(
            "src.infra.publisher.ZernioPublisher",
            side_effect=ValueError("zernio creds missing"),
        ), patch("src.infra.late.get_late_client", return_value=MagicMock()):
            pub = get_publisher("acc_x")
        # ShadowPublisher setup raised; we fall back to the primary alone.
        assert isinstance(pub, LatePublisher)

    def test_truthy_env_values_parsed(self, monkeypatch):
        from src.infra.publisher import ShadowPublisher, get_publisher

        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test")
        for val in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("PUBLISHER_SHADOW", val)
            with patch("src.infra.late.get_late_client", return_value=MagicMock()):
                pub = get_publisher("acc_x")
            assert isinstance(pub, ShadowPublisher), f"value {val!r} should enable shadow"

    def test_falsy_env_values_disable_shadow(self, monkeypatch):
        from src.infra.publisher import LatePublisher, get_publisher

        for val in ("0", "false", "no", "", "off"):
            monkeypatch.setenv("PUBLISHER_SHADOW", val)
            with patch("src.infra.late.get_late_client", return_value=MagicMock()):
                pub = get_publisher("acc_x")
            assert isinstance(pub, LatePublisher), f"value {val!r} should NOT enable shadow"
