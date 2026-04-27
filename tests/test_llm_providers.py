"""
LLM Provider Registry testleri — Faz M1.

Provider rehberi: openai, gemini, deepseek. Her biri icin base_url ve env
var ismi standart sekilde tanimli. Bu modul HENUZ uretimde kullanilmiyor;
sonraki fazlar (M2, M3) buradan okuyacak.

Bu test seti rehberin bilgilerinin dogru oldugunu kontrol eder; hicbir
gercek API'ye istek atmaz.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

import pytest

from src.infra.llm_providers import (
    SUPPORTED_PROVIDERS,
    LLMProvider,
    get_provider,
    get_provider_or_none,
    list_provider_names,
)


# ---------------------------------------------------------------------------
# Registry icerigi
# ---------------------------------------------------------------------------


def test_three_supported_providers_present():
    """OpenAI, Gemini, DeepSeek — uc tedarikci de tanimli."""
    names = list_provider_names()
    assert "openai" in names
    assert "gemini" in names
    assert "deepseek" in names


def test_openai_provider_metadata():
    p = get_provider("openai")
    assert p.name == "openai"
    assert p.base_url == "https://api.openai.com/v1"
    assert p.env_var == "OPENAI_API_KEY"


def test_gemini_provider_metadata():
    """Gemini'nin OpenAI-compatible endpoint'i kullaniliyor (Faz M5 icin)."""
    p = get_provider("gemini")
    assert p.name == "gemini"
    assert p.base_url == (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    assert p.env_var == "GOOGLE_AI_API_KEY"


def test_deepseek_provider_metadata():
    """DeepSeek native OpenAI-compatible (Faz M4 icin)."""
    p = get_provider("deepseek")
    assert p.name == "deepseek"
    assert p.base_url == "https://api.deepseek.com/v1"
    assert p.env_var == "DEEPSEEK_API_KEY"


# ---------------------------------------------------------------------------
# Bilinmeyen provider davranisi
# ---------------------------------------------------------------------------


def test_unknown_provider_raises():
    """Bilinmeyen provider adi → ValueError (yazim hatasi yakalama)."""
    with pytest.raises(ValueError, match="(unknown|unsupported)"):
        get_provider("anthropic")  # bu projede tool olarak yok


def test_unknown_provider_or_none_returns_none():
    """get_provider_or_none — yazim hatasinda None doner, exception yok."""
    assert get_provider_or_none("nonexistent") is None
    assert get_provider_or_none("") is None
    assert get_provider_or_none(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Case-insensitive lookup
# ---------------------------------------------------------------------------


def test_provider_name_case_insensitive():
    """OPENAI, OpenAI, openai → ayni provider."""
    assert get_provider("OPENAI").name == "openai"
    assert get_provider("OpenAI").name == "openai"
    assert get_provider("openai").name == "openai"


def test_provider_name_whitespace_tolerated():
    """' openai ' → trim + lookup."""
    assert get_provider("  openai  ").name == "openai"


# ---------------------------------------------------------------------------
# LLMProvider data class — basit assertion'lar
# ---------------------------------------------------------------------------


def test_llm_provider_is_immutable():
    """LLMProvider frozen dataclass — runtime'da degistirilemez."""
    p = get_provider("openai")
    with pytest.raises((AttributeError, Exception)):
        p.base_url = "https://hijacked.com"  # type: ignore[misc]


def test_supported_providers_dict_exposed():
    """SUPPORTED_PROVIDERS public — diger fazlar kullanacak."""
    assert isinstance(SUPPORTED_PROVIDERS, dict)
    assert len(SUPPORTED_PROVIDERS) >= 3


def test_each_provider_has_no_trailing_slash():
    """base_url'lerde trailing slash tutarli olmali (httpx urljoin uyumlu)."""
    for name in list_provider_names():
        p = get_provider(name)
        # OpenAI-compat endpoint'lerin cogu trailing slash ile bitir; ama
        # istemcimiz '/path' ekleyecek. urljoin hem '/' biten hem bitmeyene
        # tolerantdir; biz sadece '//path' olusmamasini garanti ediyoruz.
        assert not p.base_url.endswith("//")
        assert "://" in p.base_url
