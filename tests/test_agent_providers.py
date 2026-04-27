"""
Per-agent provider config testleri — Faz M2.

ModelSettings.agent_providers: agent isminden provider'a haritalama.
Default: hepsi 'openai' (mevcut davranisin aynisi). Firestore'da
override edilebilir.

Bu faz uretim davranisini DEGISTIRMEZ; default'lar mevcut sistemin
aynisini yansitir.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import patch

import pytest

from src.app.config import (
    ModelSettings,
    clear_model_settings_cache,
    get_agent_provider,
    get_model_settings,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_model_settings_cache()
    yield
    clear_model_settings_cache()


# ---------------------------------------------------------------------------
# Default davranis — Firestore boslugunda her agent OpenAI'da
# ---------------------------------------------------------------------------


def test_all_agents_default_to_openai_when_firestore_empty():
    """Firestore'da agentProviders yoksa, hepsi 'openai'."""
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value={},
    ):
        settings = get_model_settings()

    for agent in (
        "orchestrator",
        "image",
        "video",
        "marketing",
        "analysis",
        "customer",
    ):
        assert settings.agent_providers[agent] == "openai", (
            f"Agent {agent} default openai degil"
        )


def test_get_agent_provider_default_openai():
    """get_agent_provider() helper default'ta 'openai' doner."""
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value={},
    ):
        assert get_agent_provider("orchestrator") == "openai"
        assert get_agent_provider("customer") == "openai"


# ---------------------------------------------------------------------------
# Firestore'dan okunan override degerleri
# ---------------------------------------------------------------------------


def test_provider_override_per_agent():
    """Firestore agentProviders ile her agent'in provider'i ayri ayarlanabilir."""
    fake_doc = {
        "agentProviders": {
            "marketing": "deepseek",
            "analysis": "gemini",
            "customer": "gemini",
        }
    }
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value=fake_doc,
    ):
        settings = get_model_settings()

    assert settings.agent_providers["marketing"] == "deepseek"
    assert settings.agent_providers["analysis"] == "gemini"
    assert settings.agent_providers["customer"] == "gemini"
    # Belirtilmemisler hala openai
    assert settings.agent_providers["orchestrator"] == "openai"
    assert settings.agent_providers["image"] == "openai"


def test_unsupported_provider_falls_back_to_openai():
    """Yanlis bir provider ismi (yazim hatasi vb.) → fail-safe openai'a duser."""
    fake_doc = {
        "agentProviders": {
            "marketing": "anthropic",  # destek yok
            "analysis": "INVALID",
        }
    }
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value=fake_doc,
    ):
        settings = get_model_settings()

    # Tanimsiz/desteksiz provider → openai (mevcut davranis korunur)
    assert settings.agent_providers["marketing"] == "openai"
    assert settings.agent_providers["analysis"] == "openai"


def test_provider_lookup_case_insensitive():
    """Firestore'a yanlislikla 'DeepSeek' yazilirsa da kabul edilir."""
    fake_doc = {
        "agentProviders": {
            "marketing": "DeepSeek",
            "analysis": "  GEMINI  ",
        }
    }
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value=fake_doc,
    ):
        settings = get_model_settings()

    assert settings.agent_providers["marketing"] == "deepseek"
    assert settings.agent_providers["analysis"] == "gemini"


# ---------------------------------------------------------------------------
# Firestore hatasi durumu — fail-safe
# ---------------------------------------------------------------------------


def test_firestore_error_falls_back_to_default():
    """Firestore patlarsa hepsi openai'da kalir, sistem kirilmaz."""
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        side_effect=Exception("firebase down"),
    ):
        settings = get_model_settings()

    for agent in ("orchestrator", "marketing", "analysis", "customer"):
        assert settings.agent_providers[agent] == "openai"


# ---------------------------------------------------------------------------
# get_agent_provider helper
# ---------------------------------------------------------------------------


def test_get_agent_provider_unknown_agent_returns_openai():
    """Bilinmeyen agent ismi sorgulamasi (yazim hatasi) → openai default."""
    with patch(
        "src.app.config._load_model_settings_from_firebase",
        return_value={},
    ):
        # Tanimsiz agent → guvenli default
        assert get_agent_provider("nonexistent_agent") == "openai"


def test_model_settings_has_agent_providers_field():
    """ModelSettings dataclass agent_providers alanina sahip olmali."""
    ms = ModelSettings()
    assert hasattr(ms, "agent_providers")
    assert isinstance(ms.agent_providers, dict)
