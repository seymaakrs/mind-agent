"""OpenAI gpt-image-2 client contract tests.

Pin three production-critical invariants:

1. Aspect ratio -> OpenAI size mapping is deterministic and covers all
   public ratios the Marketing Agent uses (1:1, 4:5, 9:16, 16:9, 4:3).
2. Backend factory routes by ``image_generation_model`` prefix:
   ``gpt-image*`` -> OpenAI client, anything else -> Gemini client.
3. The generate/edit request payloads include ``quality`` and the
   resolved ``size`` — drift here silently downgrades output.

Httpx call is mocked; no real OpenAI API hit.
"""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("dotenv", reason="python-dotenv required (production deps)")

from src.infra.openai_image_client import (
    OpenAIImageClient,
    _ASPECT_TO_SIZE,
)


# ---------------------------------------------------------------------------
# 1) Aspect ratio mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ratio,expected",
    [
        ("1:1", "1024x1024"),
        ("4:5", "1024x1536"),
        ("9:16", "1024x1536"),
        ("2:3", "1024x1536"),
        ("3:4", "1024x1536"),
        ("16:9", "1536x1024"),
        ("4:3", "1536x1024"),
        ("3:2", "1536x1024"),
    ],
)
def test_aspect_ratio_maps_to_supported_size(ratio, expected):
    assert _ASPECT_TO_SIZE[ratio] == expected
    assert OpenAIImageClient._resolve_size(ratio) == expected


def test_unknown_aspect_ratio_falls_back_to_square():
    assert OpenAIImageClient._resolve_size("21:9") == "1024x1024"
    assert OpenAIImageClient._resolve_size("") == "1024x1024"


def test_resolved_sizes_are_only_openai_supported():
    """Tüm map'lenen size'lar OpenAI gpt-image API'nin kabul ettiği 3 size'dan biri olmalı."""
    allowed = {"1024x1024", "1024x1536", "1536x1024"}
    for size in _ASPECT_TO_SIZE.values():
        assert size in allowed, f"Unsupported OpenAI size in mapping: {size}"


# ---------------------------------------------------------------------------
# 2) Backend factory routing
# ---------------------------------------------------------------------------

def test_backend_factory_routes_gpt_image_to_openai(monkeypatch):
    from src.app import config as cfg
    from src.infra import image_backend

    fake_ms = MagicMock(image_generation_model="gpt-image-2",
                        image_generation_quality="high")
    monkeypatch.setattr(image_backend, "get_model_settings", lambda: fake_ms)
    monkeypatch.setattr(cfg, "get_model_settings", lambda: fake_ms)

    # OpenAIImageClient ctor only needs OPENAI_API_KEY in settings; stub it.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    fake_settings = MagicMock(openai_api_key="sk-test")
    import src.infra.openai_image_client as oic
    monkeypatch.setattr(oic, "get_settings", lambda: fake_settings)

    client = image_backend.get_image_client()
    assert client.__class__.__name__ == "OpenAIImageClient"


def test_backend_factory_routes_gemini_to_legacy(monkeypatch):
    from src.infra import image_backend

    fake_ms = MagicMock(image_generation_model="gemini-2.5-flash-image",
                        image_generation_quality="high")
    monkeypatch.setattr(image_backend, "get_model_settings", lambda: fake_ms)

    # Stub the legacy factory so we don't hit Google credentials.
    sentinel = MagicMock(name="LegacyClient")
    monkeypatch.setattr(
        "src.infra.google_ai_client.get_image_generation_client",
        lambda: sentinel,
    )
    client = image_backend.get_image_client()
    assert client is sentinel


# ---------------------------------------------------------------------------
# 3) Request payload contract — quality + size always present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_image_payload_contract(monkeypatch):
    """Request body MUST include model, prompt, size, quality, n."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    import src.infra.openai_image_client as oic

    fake_settings = MagicMock(openai_api_key="sk-test")
    monkeypatch.setattr(oic, "get_settings", lambda: fake_settings)
    fake_ms = MagicMock(image_generation_model="gpt-image-2",
                        image_generation_quality="high")
    monkeypatch.setattr(oic, "get_model_settings", lambda: fake_ms)

    captured: dict = {}
    one_pixel_png = base64.b64encode(b"\x89PNG\r\n").decode()

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"data": [{"b64_json": one_pixel_png}]}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None, data=None, files=None):
            captured.update({"url": url, "json": json, "headers": headers})
            return _FakeResp()

    monkeypatch.setattr(oic.httpx, "AsyncClient", _FakeClient)

    client = OpenAIImageClient()
    imgs = await client.generate_image("A cozy hotel by the sea", aspect_ratio="4:5")

    assert imgs and isinstance(imgs[0], bytes)
    assert captured["url"].endswith("/v1/images/generations")
    body = captured["json"]
    assert body["model"] == "gpt-image-2"
    assert body["prompt"] == "A cozy hotel by the sea"
    assert body["size"] == "1024x1536"  # 4:5 -> portrait
    assert body["quality"] == "high"
    assert body["n"] == 1
    # Auth header
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_quality_override_from_settings(monkeypatch):
    """imageGenerationQuality='medium' override edilirse payload medium gider."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    import src.infra.openai_image_client as oic

    fake_settings = MagicMock(openai_api_key="sk-test")
    monkeypatch.setattr(oic, "get_settings", lambda: fake_settings)
    fake_ms = MagicMock(image_generation_model="gpt-image-2",
                        image_generation_quality="medium")
    monkeypatch.setattr(oic, "get_model_settings", lambda: fake_ms)

    captured: dict = {}

    class _R:
        status_code = 200
        text = ""
        def json(self): return {"data": [{"b64_json": "QQ=="}]}

    class _C:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None, **kw):
            captured["body"] = json
            return _R()

    monkeypatch.setattr(oic.httpx, "AsyncClient", _C)
    await OpenAIImageClient().generate_image("test", aspect_ratio="1:1")
    assert captured["body"]["quality"] == "medium"


@pytest.mark.asyncio
async def test_non_200_raises_service_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    import src.infra.openai_image_client as oic
    from src.infra.errors import ServiceError

    fake_settings = MagicMock(openai_api_key="sk-test")
    monkeypatch.setattr(oic, "get_settings", lambda: fake_settings)
    fake_ms = MagicMock(image_generation_model="gpt-image-2",
                        image_generation_quality="high")
    monkeypatch.setattr(oic, "get_model_settings", lambda: fake_ms)

    class _R:
        status_code = 429
        text = '{"error":"rate limited"}'
        def json(self): return {}

    class _C:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _R()

    monkeypatch.setattr(oic.httpx, "AsyncClient", _C)
    with pytest.raises(ServiceError) as exc_info:
        await OpenAIImageClient().generate_image("p", aspect_ratio="1:1")
    assert exc_info.value.status_code == 429
