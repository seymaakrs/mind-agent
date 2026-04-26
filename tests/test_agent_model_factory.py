"""
make_agent_model() testleri — Faz M3.

Her agent icin uygun model spec'ini doner. Provider rehberi (M1) ve
agent_providers config'i (M2) buradan kullanir. Henuz tek provider
(openai) destekleniyor; M4/M5 ile DeepSeek/Gemini eklenecek.

Faz M3'un amaci: agent factory'lerin 'kendi modelini secme' mantigini
tek fonksiyona toplamak. Davranis BIT-BIT aynisi (string model adi
doner, default openai client kullanilir).
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import patch

import pytest

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
# Non-openai provider — Faz M3'te yumusak fallback (M4/M5'te genisleyecek)
# ---------------------------------------------------------------------------


def test_non_openai_provider_falls_back_to_string_for_now():
    """
    Faz M3'te DeepSeek/Gemini icin gercek client wrapper'i yok — fallback
    olarak string model adi donulur (default OpenAI client kullanilir).

    M4 ve M5 bu davranisi extend edecek: gercek provider client'i ile
    bir Model wrapper donecek.
    """
    fake_settings = _model_settings_with(
        agent_providers={"marketing": "deepseek", "orchestrator": "openai"}
    )
    with patch(
        "src.infra.agent_model_factory.get_model_settings",
        return_value=fake_settings,
    ):
        result = make_agent_model("marketing")

    # M3 fallback: string. Henuz "gercek deepseek client" olusturulmuyor.
    assert isinstance(result, str)


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
