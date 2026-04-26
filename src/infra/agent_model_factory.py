"""
Agent Model Factory — Faz M5 (Gemini adapter aktif).

Tek giris noktasi: make_agent_model(agent_name, override).

Provider karar sirasi:
  openai   → string model adi (SDK default client)
  gemini   → AsyncOpenAI(gemini base_url) + OpenAIChatCompletionsModel
  deepseek → key yoksa openai string fallback (M4: key gelince aktif)
  unknown  → openai string fallback (sistem kirilmaz)
"""
from __future__ import annotations

import os
from typing import Any

from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from src.app.config import ModelSettings, get_model_settings
from src.infra.llm_providers import get_provider_or_none


# ---------------------------------------------------------------------------
# Agent ismi → ModelSettings field eslestirmesi
# ---------------------------------------------------------------------------

_AGENT_TO_MODEL_FIELD: dict[str, str] = {
    "orchestrator": "orchestrator_model",
    "image": "image_agent_model",
    "video": "video_agent_model",
    "marketing": "marketing_agent_model",
    "analysis": "analysis_agent_model",
    # customer agent kendi modeli yoksa orchestrator'unkini kullanir
    "customer": "orchestrator_model",
}


def resolve_model_name(agent_name: str, settings: ModelSettings) -> str:
    """Bir agent icin ModelSettings'den model adini cikarir.

    Bilinmeyen agent → 'gpt-4o' (guvenli OpenAI default).
    """
    field_name = _AGENT_TO_MODEL_FIELD.get(agent_name)
    if field_name is None:
        return "gpt-4o"
    return getattr(settings, field_name, "gpt-4o") or "gpt-4o"


def _make_custom_provider_model(
    provider_name: str,
    model_name: str,
) -> OpenAIChatCompletionsModel | str:
    """OpenAI-compatible provider icin client + wrapper olusturur.

    API key env var'i set degilse sessizce string fallback yapar —
    provider config hatasi uretimi durdurmasin.
    """
    provider = get_provider_or_none(provider_name)
    if provider is None:
        return model_name

    api_key = os.environ.get(provider.env_var)
    if not api_key:
        return model_name

    client = AsyncOpenAI(base_url=provider.base_url, api_key=api_key)
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def make_agent_model(
    agent_name: str,
    override: str | None = None,
) -> str | Any:
    """Bir agent icin Agent(model=...) parametresine verilecek deger.

    Args:
        agent_name: 'orchestrator', 'image', 'video', 'marketing', 'analysis',
            'customer'.
        override: Explicit model adi (varsa config + provider'i ezer).

    Returns:
        openai provider   → string model adi (SDK default client)
        gemini/deepseek   → OpenAIChatCompletionsModel (key varsa)
        key yoksa/unknown → string fallback (sistem kirilmaz)
    """
    if override:
        return override

    settings = get_model_settings()
    model_name = resolve_model_name(agent_name, settings)
    provider_name = settings.agent_providers.get(agent_name, "openai")

    if provider_name == "openai":
        return model_name

    return _make_custom_provider_model(provider_name, model_name)


__all__ = [
    "make_agent_model",
    "resolve_model_name",
]
