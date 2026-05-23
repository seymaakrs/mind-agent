"""Snapshot tests that freeze the Publisher layer's public shape.

These tests are intentionally strict: they exist so that a downstream
consumer (Firestore writers, agent prompts, mind-id portal) cannot be
silently broken by a refactor to ``PublishResult.to_dict()`` or to the
``orchestrator`` tool-layer return shape.

When you intentionally change the shape, update the EXPECTED_* sets here
in the same PR — the failure mode is the test, not production.
"""
from __future__ import annotations

import pytest

from src.infra.publisher.base import PublishResult


# ---------------------------------------------------------------------------
# C-1 — PublishResult.to_dict() shape contract
# ---------------------------------------------------------------------------

# Keys that MUST appear on every success serialization.
SUCCESS_REQUIRED_KEYS = frozenset(
    {"success", "post_id", "platform_post_id", "platform_post_url", "status"}
)
# Keys that MAY appear on a success serialization (only when their underlying
# attribute is not None). Tests below assert the optional branches.
SUCCESS_OPTIONAL_KEYS = frozenset({"type", "item_count", "published_at"})

# Keys that MUST appear on every failure serialization (in addition to the
# required success keys above).
FAILURE_REQUIRED_EXTRA = frozenset({"error", "status_code"})


def test_to_dict_success_minimal_has_exactly_required_keys():
    r = PublishResult(
        success=True,
        post_id="post_123",
        platform_post_id="ig_abc",
        platform_post_url="https://instagram.com/p/abc",
        status="published",
    )
    d = r.to_dict()
    assert set(d.keys()) == SUCCESS_REQUIRED_KEYS
    assert d["success"] is True


def test_to_dict_success_full_includes_documented_optionals_only():
    r = PublishResult(
        success=True,
        post_id="post_123",
        platform_post_id="ig_abc",
        platform_post_url="https://instagram.com/p/abc",
        status="published",
        type="carousel",
        item_count=4,
        published_at="2026-05-23T11:00:00Z",
    )
    d = r.to_dict()
    assert set(d.keys()) == SUCCESS_REQUIRED_KEYS | SUCCESS_OPTIONAL_KEYS
    assert d["type"] == "carousel"
    assert d["item_count"] == 4
    assert d["published_at"] == "2026-05-23T11:00:00Z"


@pytest.mark.parametrize(
    "field,value",
    [("type", "story"), ("item_count", 3), ("published_at", "2026-05-23T11:00:00Z")],
)
def test_to_dict_success_optional_only_when_set(field, value):
    r = PublishResult(
        success=True,
        post_id="p",
        platform_post_id="pp",
        platform_post_url="u",
        status="published",
        **{field: value},
    )
    d = r.to_dict()
    assert field in d
    other_optionals = SUCCESS_OPTIONAL_KEYS - {field}
    for k in other_optionals:
        assert k not in d, f"{k} leaked into the dict without being set"


def test_to_dict_failure_includes_error_and_status_code():
    r = PublishResult(
        success=False,
        post_id=None,
        platform_post_id=None,
        platform_post_url=None,
        status="failed",
        error="429 Too Many Requests",
        status_code=429,
    )
    d = r.to_dict()
    assert set(d.keys()) == SUCCESS_REQUIRED_KEYS | FAILURE_REQUIRED_EXTRA
    assert d["success"] is False
    assert d["error"] == "429 Too Many Requests"
    assert d["status_code"] == 429


def test_to_dict_failure_omits_unset_error_fields():
    r = PublishResult(success=False, status="failed")
    d = r.to_dict()
    # success-required keys always present, but optional error fields omitted
    assert set(d.keys()) == SUCCESS_REQUIRED_KEYS


# ---------------------------------------------------------------------------
# C-2 — Tool layer return shape contract
# ---------------------------------------------------------------------------

# When the Instagram orchestrator tool publishes successfully, downstream
# consumers (Firestore writers, prompt templates referencing $.post_url,
# agent retry logic checking $.success) rely on this exact key set. The
# ``late_post_id`` name is deliberately preserved as a backwards-compat shim
# from the Late → Zernio migration (see src/tools/orchestrator/instagram.py).
ORCHESTRATOR_INSTAGRAM_SUCCESS_KEYS = frozenset(
    {
        "success",
        "post_id",
        "late_post_id",
        "post_url",
        "content_type",
        "is_story",
        "message",
    }
)


@pytest.mark.asyncio
async def test_orchestrator_instagram_post_success_shape(monkeypatch):
    """Freeze the success-path dict shape returned by post_to_instagram."""
    pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")
    from src.tools.orchestrator import instagram as ig_mod

    class _StubPublisher:
        backend = "zernio"

        async def instagram_post(self, **kwargs):
            return PublishResult(
                success=True,
                post_id="zernio_post_abc",
                platform_post_id="ig_native_xyz",
                platform_post_url="https://instagram.com/p/xyz",
                status="published",
                type="image",
            )

    monkeypatch.setattr(ig_mod, "get_publisher", lambda _: _StubPublisher())

    result = await ig_mod.post_to_instagram(
        file_url="https://cdn.example/image.jpg",
        caption="test",
        content_type="image",
        instagram_id="acc_test",
    )

    assert set(result.keys()) == ORCHESTRATOR_INSTAGRAM_SUCCESS_KEYS, (
        f"Tool return shape drifted. Got: {sorted(result.keys())}. "
        f"Update ORCHESTRATOR_INSTAGRAM_SUCCESS_KEYS only when downstream "
        f"consumers are also updated."
    )
    assert result["success"] is True
    assert result["post_id"] == "ig_native_xyz"  # ← platform-native id, not internal
    assert result["late_post_id"] == "zernio_post_abc"  # ← backwards-compat shim
    assert result["post_url"] == "https://instagram.com/p/xyz"
    assert result["content_type"] == "image"
    assert result["is_story"] is False
    assert "Successfully posted" in result["message"]
