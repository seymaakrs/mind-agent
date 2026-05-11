"""Fallback templates — used when NocoDB ``message_templates`` is empty/missing.

Mirrors Seyma's ``lead_monitor.py`` 3-variant pool but extended with intent
branches. Each entry is a *base template*; the LLM (responder.py) rephrases
it into a natural reply so Meta's spam filter sees variation across sends.
"""
from __future__ import annotations


FALLBACK_TEMPLATES: dict[str, list[str]] = {
    "olumlu": [
        "Cok tesekkurler ilginize! Slowdays ekibi olarak size yuz yuze "
        "detayli anlatmak isteriz. Bu hafta icinde uygun bir gun var mi?",
        "Harika! Size kisaya ozel bir tanitim hazirladik. Kisa bir gorusme "
        "icin musait oldugunuz bir zaman var mi?",
        "Sevindik! Slowdays'in otelinize ne katacagini kahve eslginde "
        "anlatabiliriz. Hangi gun uygun olursunuz?",
    ],
    "soru": [
        "Sorunuz icin tesekkurler! En dogru cevabi vermek icin size kisa bir "
        "gorusmede detay verebilir miyim?",
        "Iyi soru, kisa bir gorusmede aciklamasi daha kolay. Bu hafta "
        "musait oldugunuz bir vakit var mi?",
    ],
    "olumsuz": [
        # Empty — olumsuz mesajlara yanit verme; lead'i 'Soguk'a flag.
    ],
    "spam": [
        # Empty — spam'a yanit verme.
    ],
}


def has_active_templates(intent: str) -> bool:
    """True if there is at least one fallback template for this intent."""
    return bool(FALLBACK_TEMPLATES.get(intent))


__all__ = ["FALLBACK_TEMPLATES", "has_active_templates"]
