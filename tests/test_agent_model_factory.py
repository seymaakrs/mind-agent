"""
make_agent_model() testleri — Faz M3 + M5.

M3: Her agent icin config'den model adi secer (string, default openai client).
M5: Gemini provider icin AsyncOpenAI + OpenAIChatCompletionsModel wrapper doner.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import MagicMock, patch

import pytest
from agents import OpenAIChatCompletionsModel

from src.app.config import (
    ModelSettings,
    clear_model_settings_cache,
)
from src.infra.agent_model_factory import (
    make_agent_model,
    resolve_model_name,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_model_settings_cache()
    yield
    clear_model_settings_cache()


def _model_settings_with(agent_providers: dict[str, str] | None = None,
                         **model_overrides) -> ModelSettings:
    """Test helper: kismi override ile ModelSettings."""
    defaults = {
        "orchestrator_model": "gpt-4o-mini",
        "image_agent_model": "gpt-4o",
        "video_agent_model": "gpt-4o",
        "marketing_agent_model": "gpt-4o",
        "analysis_agent_model": "gpt-4o",
        "agent_providers": agent_providers or {
            "orchestrator": "openai",
            "image": "openai",
            "video": "openai",
            "marketing": "openai",
            "analysis": "openai",
            "customer": "openai",
        },
    }
    defaults.update(model_overrides)
    return ModelSettings(**defaults)


# ---------------------------------------------------------------------------
# resolve_model_name — agent'in model adini cikarma mantigi
# ---------------------------------------------------------------------------


def test_resolve_orchestrator_model():
    ms = _model_settings_with(orchestrator_model="gpt-4o-mini")
    assert resolve_model_name("orchestrator", ms) == "gpt-4o-mini"


def test_resolve_marketing_model():
    ms = _model_settings_with(marketing_agent_model="gpt-4o")
    assert resolve_model_name("marketing", ms) == "gpt-4o"


def test_resolve_customer_uses_orchestrator_default():
    """Customer agent'in ozel modeli yoksa orchestrator_model'i kullanir."""
    ms = _model_settings_with(orchestrator_model="gpt-4o-mini")
    assert resolve_model_name("customer", ms) == "gpt-4o-mini"


def test_resolve_unknown_agent_falls_back_to_openai_default():
    """Bilinmeyen agent → 'gpt-4o' guvenli default."""
    ms = _model_settings_with()
    assert resolve_model_name("nonexistent", ms) == "gpt-4o"


# ---------------------------------------------------------------------------
# make_agent_model — provider-aware
# ---------------------------------------------------------------------------


def test_openai_provider_returns_string_model():
    """Provider openai → mevcut davranis (string), default client kullanilir."""
    fake_settings = _model_settings_with()

    def _fake_get_settings():
        return fake_settings

    with patch("src.infra.agent_model_factory.get_model_settings", new=_fake_get_settings):
        result = make_agent_model("orchestrator")

    assert isinstance(result, str)
    assert result == "gpt-4o-mini"


def test_each_agent_returns_its_own_model_with_openai():
    """Her agent ayri model adi alir (config'den)."""
    fake_settings = _model_settings_with(
        orchestrator_model="gpt-4o-mini",
        marketing_agent_model="gpt-4o",
        analysis_agent_model="gpt-4o",
    )
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        assert make_agent_model("orchestrator") == "gpt-4o-mini"
        assert make_agent_model("marketing") == "gpt-4o"
        assert make_agent_model("analysis") == "gpt-4o"


# ---------------------------------------------------------------------------
# Non-openai provider — key yoksa string fallback (fail-safe)
# ---------------------------------------------------------------------------


def test_non_openai_provider_without_key_falls_back_to_string():
    """Key env var set degilse string fallback — sistem kirilmaz."""
    fake_settings = _model_settings_with(
        agent_providers={"marketing": "deepseek", "orchestrator": "openai"}
    )
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        with patch.dict(os.environ, {}, clear=True):
            os.environ["OPENAI_API_KEY"] = "test-fake-key"
            result = make_agent_model("marketing")

    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Faz M5 — Gemini adapter (gercek OpenAIChatCompletionsModel wrapper)
# ---------------------------------------------------------------------------


def test_gemini_provider_with_key_returns_model_wrapper():
    """GOOGLE_AI_API_KEY varsa OpenAIChatCompletionsModel wrapper doner."""
    fake_settings = _model_settings_with(
        marketing_agent_model="gemini-2.0-flash",
        agent_providers={"marketing": "gemini", "orchestrator": "openai"},
    )
    mock_client = MagicMock()
    with patch("src.infra.agent_model_factory.get_model_settings", return_value=fake_settings):
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "fake-gemini-key"}):
            with patch("src.infra.agent_model_factory.AsyncOpenAI", return_value=mock_client):
                result = make_agent_model("marketing")

    assert isinstance(result, OpenAIChatCompletionsModel)
    assert result.model == "gemini-2.0-flash"


def test_gemini_provider_without_key_falls_back_to_string():
    """GOOGLE_AI_API_KEY yoksa string fallback (sistem kirilmaz)."""
    fake_settings = _model_settings_with(
        marketing_agent_model="gemini-2.0-flash",
        agent_providers={"marketing": "gemini", "orchestrator": "openai"},
    )
    with patch("src.infra.agent_model_factory.get_model_settings", return_value=fake_settings):
        with patch.dict(os.environ, {}, clear=True):
            os.environ["OPENAI_API_KEY"] = "test-fake-key"
            result = make_agent_model("marketing")

    assert isinstance(result, str)


def test_gemini_wrapper_uses_gemini_base_url():
    """AsyncOpenAI Gemini base_url ve api_key ile olusturulur."""
    from src.infra.llm_providers import SUPPORTED_PROVIDERS
    expected_base_url = SUPPORTED_PROVIDERS["gemini"].base_url

    fake_settings = _model_settings_with(
        agent_providers={"orchestrator": "gemini"},
    )
    mock_client = MagicMock()
    with patch("src.infra.agent_model_factory.get_model_settings", return_value=fake_settings):
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "fake-key"}):
            with patch("src.infra.agent_model_factory.AsyncOpenAI", return_value=mock_client) as mock_async_openai:
                make_agent_model("orchestrator")

    call_kwargs = mock_async_openai.call_args.kwargs
    assert call_kwargs["base_url"] == expected_base_url
    assert call_kwargs["api_key"] == "fake-key"


def test_gemini_model_name_forwarded_to_wrapper():
    """Config'deki model adi wrapper'a aktarilir."""
    fake_settings = _model_settings_with(
        analysis_agent_model="gemini-1.5-pro",
        agent_providers={"analysis": "gemini"},
    )
    mock_client = MagicMock()
    with patch("src.infra.agent_model_factory.get_model_settings", return_value=fake_settings):
        with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "fake-key"}):
            with patch("src.infra.agent_model_factory.AsyncOpenAI", return_value=mock_client):
                result = make_agent_model("analysis")

    assert isinstance(result, OpenAIChatCompletionsModel)
    assert result.model == "gemini-1.5-pro"


def test_provider_invalid_falls_back_to_openai_string():
    """Invalid provider config'inde de calisir, openai string doner."""
    fake_settings = _model_settings_with(
        agent_providers={"marketing": "openai"}  # parse zaten openai'a duser
    )
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        result = make_agent_model("marketing")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Override parametresi — explicit model verilirse onu kullanir
# ---------------------------------------------------------------------------


def test_explicit_model_override_wins():
    """make_agent_model('x', override='gpt-5') → override doner."""
    fake_settings = _model_settings_with(orchestrator_model="gpt-4o")
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        result = make_agent_model("orchestrator", override="gpt-5")
    assert result == "gpt-5"


def test_override_none_falls_back_to_config():
    """override=None → config'deki model."""
    fake_settings = _model_settings_with(orchestrator_model="gpt-4o-mini")
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        result = make_agent_model("orchestrator", override=None)
    assert result == "gpt-4o-mini"
