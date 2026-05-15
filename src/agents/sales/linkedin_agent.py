"""LinkedIn Mesaj Motoru Agent.

LinkedIn outreach'in deger ureten kismini (dogru kisiye dogru, kisisellestirilmis
mesaj) uretir. LinkedIn'de profil ARAMAZ, baglanti istegi/DM ATMAZ — sadece
mesaj uretir ve NocoDB Etkilesimler tablosuna 'Giden / taslak' olarak yazar.
Gercek gonderim insan (Seyma/asistan) veya ileride secilecek arac ile yapilir.

Kapsam disi:
- LinkedIn arama/scraping ve gonderim (ToS / arac karari).
- Profil optimizasyonu (ayri copywriting isi).
- Otomatik zamanlama/sequence motoru.
"""
from __future__ import annotations

from typing import Any

from agents import Agent

from src.app.config import get_settings, get_model_settings
from src.tools.sales.nocodb_tools import get_nocodb_tools
from src.agents.instructions.sales import LINKEDIN_AGENT_INSTRUCTIONS


def create_linkedin_agent(
    model: str | None = None,
) -> Agent[dict[str, Any]]:
    """
    LinkedIn Mesaj Motoru Agent: lead/kisi bilgisinden kisisellestirilmis
    baglanti notu + 3 adimli takip dizisi + yanit taslaklari uretir ve
    NocoDB'ye 'Giden / taslak' olarak yazar. Gonderim bu agent'in isi DEGIL.

    Args:
        model: Opsiyonel model override.
    """
    settings = get_settings()
    model_settings = get_model_settings()

    tools = list(get_nocodb_tools())

    return Agent(
        name="linkedin",
        handoff_description=(
            "LinkedIn mesaj motoru: lead bilgisinden kisisellestirilmis "
            "baglanti notu + takip dizisi + yanit taslaklari uretir, NocoDB'ye "
            "taslak yazar. Gonderim yapmaz."
        ),
        instructions=LINKEDIN_AGENT_INSTRUCTIONS,
        tools=tools,
        tool_use_behavior="run_llm_again",
        output_type=str,
        model=model or model_settings.marketing_agent_model or settings.openai_model,
    )


__all__ = ["create_linkedin_agent"]
