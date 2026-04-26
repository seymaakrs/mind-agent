"""
Agent Model Factory — Faz M3 (Multi-Provider Migration).

Tek giris noktasi: make_agent_model(agent_name, override). Bir agent icin
'hangi modeli, hangi provider ile' kararini buradan cikariyoruz.

Faz M3 (su an):
  - Tum agent'lar 'openai' provider'ini kullaniyor (Faz M2 default).
  - make_agent_model() string model adi doner (mevcut davranis).
  - Default OpenAI client (set_default_openai_key uzerinden) kullanilir.

Faz M4 (DeepSeek key gelince):
  - Provider 'deepseek' ise: AsyncOpenAI(base_url=..., api_key=...) ile
    custom client + OpenAIChatCompletionsModel wrapper donulecek.

Faz M5 (Gemini key gelince):
  - Aynisi gemini icin.

Onemli: Bu fonksiyon davranis-koruyucu refactor zemini. M3'te uretimde
hicbir sey degismez; M4/M5 ile yeni return path'leri eklenir.
"""
from __future__ import annotations

from typing import Any

from src.app.config import ModelSettings, get_model_settings


# ---------------------------------------------------------------------------
# Agent ismi → ModelSettings field eslestirmesi
# ---------------------------------------------------------------------------
#
# ModelSettings field isimlendirmesi tutarsiz (orchestrator_model,
# image_agent_model, marketing_agent_model). Bu eslestirme tek dogru
# kaynagi (single source of truth) olusturur.

_AGENT_TO_MODEL_FIELD: dict[str, str] = {
    "orchestrator": "orchestrator_model",
    "image": "image_agent_model",
    "video": "video_agent_model",
    "marketing": "marketing_agent_model",
    "analysis": "analysis_agent_model",
    # customer agent kendi modelini sectisi yoksa orchestrator'unkini kullanir
    # (kucuk + ucuz model, customer agent task'lari basit).
    "customer": "orchestrator_model",
}


def resolve_model_name(agent_name: str, settings: ModelSettings) -> str:
    """
    Bir agent icin ModelSettings'den model adini cikarir.

    Bilinmeyen agent → 'gpt-4o' (en guvenli OpenAI default).
    """
    field_name = _AGENT_TO_MODEL_FIELD.get(agent_name)
    if field_name is None:
        return "gpt-4o"
    return getattr(settings, field_name, "gpt-4o") or "gpt-4o"


def make_agent_model(
    agent_name: str,
    override: str | None = None,
) -> str | Any:
    """
    Bir agent icin Agent(model=...) parametresine verilecek deger.

    Args:
        agent_name: 'orchestrator', 'image', 'video', 'marketing', 'analysis',
            'customer'.
        override: Explicit model adi (varsa config + provider'i ezer).

    Returns:
        Faz M3 (su an): string model adi (OpenAI default client kullanilir).
        Faz M4/M5: provider 'deepseek' veya 'gemini' ise OpenAIChatCompletionsModel
            wrapper'i (custom client'li) donecek.

    Bilinmeyen provider → openai fallback (sistem kirilmaz).
    """
    if override:
        return override

    settings = get_model_settings()
    model_name = resolve_model_name(agent_name, settings)

    provider_name = settings.agent_providers.get(agent_name, "openai")

    if provider_name == "openai":
        # Mevcut davranis: string model adi → SDK default client'i kullanir.
        return model_name

    # M4/M5'te genisleyecek path. Su an deepseek/gemini icin de openai
    # default client kullanilir (yumusak fallback). Bu, M3 davranis-
    # koruyucu refactor sayesinde uretimi etkilemez.
    return model_name


__all__ = [
    "make_agent_model",
    "resolve_model_name",
]
