"""
LLM Provider Registry — Faz M1 (Multi-Provider Migration).

Mind-agent'in destekledigi LLM saglayicilarinin merkezi rehberi. Her provider
icin: kanonik isim, OpenAI-compatible base URL, API key env var ismi.

Bu rehber HENUZ uretimde kullanilmiyor. Sonraki fazlar buradan okur:
- Faz M2: Per-agent provider config (settings/app_settings)
- Faz M3: make_client(provider, model) → bu rehbere bakar
- Faz M4: DeepSeek provider canli baglanti (key gelince)
- Faz M5: Gemini provider canli baglanti (key gelince)

Desteklenen 3 provider'in hepsi OpenAI-compatible endpoint'e sahip — bu
sayede tek bir 'openai' kutuphanesi ile uc tedarikciye de istek atabiliriz.
Sadece base_url ve api_key degisir.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMProvider:
    """Bir LLM saglayicisinin baglanti meta-bilgileri.

    frozen=True: runtime'da degistirilemez (yanlislikla overwrite koruma).
    """

    name: str
    base_url: str
    env_var: str
    description: str = ""


# ---------------------------------------------------------------------------
# Desteklenen saglayicilar
# ---------------------------------------------------------------------------
#
# Her provider'in OpenAI-compatible API sundugu varsayilir; bu sayede
# 'openai' Python kutuphanesi (AsyncOpenAI) tum uclerine de calisir.
#
# - OpenAI         : ana platform, prod'da bu kullaniliyor.
# - Gemini         : Google'in OpenAI-compatible bridge endpoint'i.
#                    (https://ai.google.dev/gemini-api/docs/openai)
# - DeepSeek       : OpenAI-compatible API native (en uygun fiyat).
#                    (https://api-docs.deepseek.com/)

SUPPORTED_PROVIDERS: dict[str, LLMProvider] = {
    "openai": LLMProvider(
        name="openai",
        base_url="https://api.openai.com/v1",
        env_var="OPENAI_API_KEY",
        description="OpenAI — gpt-4o, gpt-4o-mini, o1, etc.",
    ),
    "gemini": LLMProvider(
        name="gemini",
        # Google'in OpenAI-uyumlu kopru endpoint'i.
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        env_var="GOOGLE_AI_API_KEY",
        description="Google Gemini — 2.0 Flash, 1.5 Pro (OpenAI-compat).",
    ),
    "deepseek": LLMProvider(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        env_var="DEEPSEEK_API_KEY",
        description="DeepSeek — chat (V3), reasoner (R1) (OpenAI-compat).",
    ),
}


def list_provider_names() -> list[str]:
    """Desteklenen tum provider isimlerini doner."""
    return list(SUPPORTED_PROVIDERS.keys())


def get_provider(name: str) -> LLMProvider:
    """
    Provider'i isimle getirir. Bilinmiyorsa ValueError firlatir.

    Lookup case-insensitive ve whitespace-tolerant — 'OpenAI', ' openai ' ayni
    sonucu verir. Bu, Firestore'a yanlislikla buyuk harf yazilmasina karsi
    savunma.
    """
    if not isinstance(name, str):
        raise ValueError(f"Provider name must be a string; got {type(name).__name__}.")
    key = name.strip().lower()
    if key not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown / unsupported LLM provider: {name!r}. "
            f"Supported: {sorted(SUPPORTED_PROVIDERS.keys())}"
        )
    return SUPPORTED_PROVIDERS[key]


def get_provider_or_none(name: str | None) -> LLMProvider | None:
    """get_provider'in exception-suz versiyonu — fallback'ler icin."""
    if not name or not isinstance(name, str):
        return None
    try:
        return get_provider(name)
    except ValueError:
        return None


__all__ = [
    "LLMProvider",
    "SUPPORTED_PROVIDERS",
    "list_provider_names",
    "get_provider",
    "get_provider_or_none",
]
