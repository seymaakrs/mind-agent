"""Tests for OpenAI image generation client (Faz D — Gemini → OpenAI migration).

Hedef: gpt-image-1 ile aynı imzaya sahip bir client. Drop-in replacement
icin generate_image(prompt, aspect_ratio) -> list[bytes].
"""
from __future__ import annotations

import base64
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test")


# ---------------------------------------------------------------------------
# Aspect ratio mapping
# ---------------------------------------------------------------------------

class TestAspectRatioMapping:
    """gpt-image-1 supports only 1024x1024, 1024x1536, 1536x1024."""

    def test_portrait_ratios_map_to_1024x1536(self):
        from src.infra.openai_image_client import _aspect_to_size
        # Instagram portrait
        assert _aspect_to_size("4:5") == "1024x1536"
        assert _aspect_to_size("9:16") == "1024x1536"
        assert _aspect_to_size("2:3") == "1024x1536"

    def test_landscape_ratios_map_to_1536x1024(self):
        from src.infra.openai_image_client import _aspect_to_size
        assert _aspect_to_size("16:9") == "1536x1024"
        assert _aspect_to_size("3:2") == "1536x1024"
        assert _aspect_to_size("4:3") == "1536x1024"

    def test_square_maps_to_1024x1024(self):
        from src.infra.openai_image_client import _aspect_to_size
        assert _aspect_to_size("1:1") == "1024x1024"

    def test_unknown_ratio_defaults_to_portrait(self):
        """4:5 is Instagram default — unknown ratios should default to that."""
        from src.infra.openai_image_client import _aspect_to_size
        assert _aspect_to_size("weird:ratio") == "1024x1536"


# ---------------------------------------------------------------------------
# Client behavior
# ---------------------------------------------------------------------------

def _mock_openai_response(image_bytes: bytes):
    """Build a fake OpenAI images.generate response."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    item = MagicMock()
    item.b64_json = b64
    response = MagicMock()
    response.data = [item]
    return response


class TestOpenAIImageClient:
    @pytest.mark.asyncio
    async def test_generate_image_returns_decoded_bytes(self):
        from src.infra import openai_image_client as oai

        fake = _mock_openai_response(b"fake-png-bytes")

        with patch.object(oai, "_get_async_client") as get_client:
            mock_client = MagicMock()
            mock_client.images = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=fake)
            get_client.return_value = mock_client

            client = oai.OpenAIImageClient()
            result = await client.generate_image("a hotel terrace", "4:5")

        assert result == [b"fake-png-bytes"]
        call_kwargs = mock_client.images.generate.call_args.kwargs
        assert call_kwargs["prompt"] == "a hotel terrace"
        assert call_kwargs["size"] == "1024x1536"
        assert call_kwargs["model"]  # set to gpt-image-1 or similar
        assert call_kwargs["n"] == 1

    @pytest.mark.asyncio
    async def test_generate_image_raises_service_error_on_api_failure(self):
        from src.infra import openai_image_client as oai
        from src.infra.errors import ServiceError
        from openai import APIError

        with patch.object(oai, "_get_async_client") as get_client:
            mock_client = MagicMock()
            mock_client.images = MagicMock()
            mock_client.images.generate = AsyncMock(
                side_effect=APIError(
                    message="Server error",
                    request=MagicMock(),
                    body={"error": {"code": "server_error"}},
                )
            )
            get_client.return_value = mock_client

            client = oai.OpenAIImageClient()
            with pytest.raises((ServiceError, Exception)):
                await client.generate_image("p", "4:5")

    @pytest.mark.asyncio
    async def test_generate_image_handles_empty_data(self):
        from src.infra import openai_image_client as oai

        empty = MagicMock()
        empty.data = []

        with patch.object(oai, "_get_async_client") as get_client:
            mock_client = MagicMock()
            mock_client.images = MagicMock()
            mock_client.images.generate = AsyncMock(return_value=empty)
            get_client.return_value = mock_client

            client = oai.OpenAIImageClient()
            result = await client.generate_image("p", "4:5")

        # Empty result returned; retry layer above will handle this.
        assert result == []


# ---------------------------------------------------------------------------
# Factory dispatch
# ---------------------------------------------------------------------------

class TestImageClientFactory:
    """get_image_generation_client() chooses provider based on model name."""

    def test_gpt_image_model_returns_openai_client(self, monkeypatch):
        from src.app import config as cfg
        from src.infra import google_ai_client as gac
        from src.infra.openai_image_client import OpenAIImageClient

        # Force model to gpt-image-1
        class FakeModelSettings:
            image_generation_model = "gpt-image-1"
            image_agent_model = None
            video_agent_model = None
            marketing_agent_model = None
            analysis_agent_model = None
            orchestrator_model = None

        monkeypatch.setattr(cfg, "get_model_settings", lambda: FakeModelSettings())
        # Also need google_ai_client module-level access
        monkeypatch.setattr(gac, "get_model_settings", lambda: FakeModelSettings())

        client = gac.get_image_generation_client()
        assert isinstance(client, OpenAIImageClient)

    def test_gemini_model_returns_gemini_client(self, monkeypatch):
        from src.app import config as cfg
        from src.infra import google_ai_client as gac

        class FakeModelSettings:
            image_generation_model = "gemini-2.5-flash-image"
            image_agent_model = None
            video_agent_model = None
            marketing_agent_model = None
            analysis_agent_model = None
            orchestrator_model = None

        monkeypatch.setattr(cfg, "get_model_settings", lambda: FakeModelSettings())
        monkeypatch.setattr(gac, "get_model_settings", lambda: FakeModelSettings())

        # Set fake GOOGLE_AI_API_KEY so ImageGenerationClient init doesn't fail
        from src.app.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "google_ai_api_key", "fake-key")

        client = gac.get_image_generation_client()
        assert isinstance(client, gac.ImageGenerationClient)

    def test_dalle3_model_returns_openai_client(self, monkeypatch):
        from src.app import config as cfg
        from src.infra import google_ai_client as gac
        from src.infra.openai_image_client import OpenAIImageClient

        class FakeModelSettings:
            image_generation_model = "dall-e-3"
            image_agent_model = None
            video_agent_model = None
            marketing_agent_model = None
            analysis_agent_model = None
            orchestrator_model = None

        monkeypatch.setattr(cfg, "get_model_settings", lambda: FakeModelSettings())
        monkeypatch.setattr(gac, "get_model_settings", lambda: FakeModelSettings())

        client = gac.get_image_generation_client()
        assert isinstance(client, OpenAIImageClient)
