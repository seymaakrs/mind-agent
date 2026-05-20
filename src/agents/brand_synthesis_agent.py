"""Brand Synthesis Agent (Faz B1).

Bu ajan ham isletme verisini (Firestore businesses/{id} + serbest 'profile'
map'i + varsa eski brand_identity) okuyup kanonik BrandIdentity onerisini
'ai_synthesis' kaynagi ile Firestore'a yazar.

Tek SoT (Source of Truth) kurma adimi: Image / Video / Marketing ajanlari
bundan sonra brand_identity dokumanindan okuyacak — Faz C entegrasyonu.

Yapilmayanlar (kapsam disi):
- mind-id formu (Faz B2): kullanici elle duzenler.
- Image/Video/Marketing prompt enjeksiyonu (Faz C).
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.brand import fetch_brand_identity, update_brand_identity
from src.tools.orchestrator_tools import fetch_business
from src.agents.instructions import BRAND_SYNTHESIS_AGENT_INSTRUCTIONS


def create_brand_synthesis_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """Brand Synthesis ajani — ham veriden BrandIdentity sentezler.

    Tools:
        - fetch_business: businesses/{id} ham dokuman.
        - fetch_brand_identity: varsa onceki brand_identity.
        - update_brand_identity: sentezlenen alanlari Firestore'a yazar
          (source='ai_synthesis').

    Args:
        model: Opsiyonel model override (varsayilan: analysis_agent_model
            veya openai_model — yapilandirilmis tutarli model).
    """
    settings = get_settings()
    model_settings = get_model_settings()

    tools = [
        fetch_business,
        fetch_brand_identity,
        update_brand_identity,
    ]

    return Agent(
        name="brand_synthesis",
        handoff_description=(
            "Marka kimligi sentezleme ajani — isletmenin dagilmis bilgilerinden "
            "kanonik BrandIdentity dokumanini olusturur."
        ),
        instructions=BRAND_SYNTHESIS_AGENT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=(
            model
            or model_settings.analysis_agent_model
            or settings.openai_model
        ),
    )


__all__ = ["create_brand_synthesis_agent"]
