"""LLM-driven intent classification + reply rephrase.

Tek bir OpenAI Agents SDK call. Pydantic structured output:

    AutoReplyDecision(intent, reply_text, confidence, objection_type)

intent in {"olumlu", "olumsuz", "soru", "spam", "itiraz"}.

olumlu/soru/itiraz: reply_text doludur, musteriye GONDERILIR (runner
should_send, confidence >= 0.5). itiraz icin ek olarak ``objection_type``
siniflandirilir ve cevap ``ITIRAZ_PLAYBOOK`` anchor'larina dayanir.
olumsuz/spam: reply_text bos, yanit yok.

Insan onayi YOKTUR — itiraz cevabi da sistemce kararlastirilip dogrudan
musteriye gider.

KONUSMA HAFIZASI: ``conversation_history`` opsiyonel parametresiyle
responder onceki Gelen+Giden mesajlari (kronolojik) prompt'a anchor olarak
alir. Boylece musteri haftalar sonra geri yazdiginda ajan onu taniyor gibi
davranir, tekrar etmez. None birakilirsa eski davranis aynen calisir.
"""
from __future__ import annotations

import random
from typing import Any, Literal

from agents import Agent, Runner
from pydantic import BaseModel, Field

from .policy import AutoReplyConfig
from .templates import FALLBACK_TEMPLATES, ITIRAZ_PLAYBOOK


Intent = Literal["olumlu", "olumsuz", "soru", "spam", "itiraz"]
ObjectionType = Literal[
    "fiyat", "rekabet", "erteleme", "olcek", "teknoloji", "kanit"
]


class AutoReplyDecision(BaseModel):
    intent: Intent = Field(
        description="Inbound mesajin niyeti. olumlu=ilgi var, soru=bilgi "
        "soruyor, olumsuz=red/iptal, spam=alakasiz, itiraz=fiyat/rekabet/"
        "kanit/erteleme/olcek/teknoloji itirazi."
    )
    reply_text: str = Field(
        default="",
        description="TR yanit. olumlu/soru/itiraz: musteriye GIDECEK yanit "
        "(otomatik gonderilir). olumsuz/spam: BOS birak.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Siniflandirma guven skoru 0-1. <0.5 ise yanit gitmez.",
    )
    objection_type: ObjectionType | None = Field(
        default=None,
        description="Sadece intent=itiraz iken doldur: itirazin tipi.",
    )


_INSTRUCTIONS = """\
Sen Slowdays satis ekibinin WhatsApp asistanisin. Otel sahiplerinden gelen
inbound mesajlari okur, niyetini siniflandirir ve KISA, SAMIMI, TR bir yanit
yazarsin. Yanitin DOGRUDAN musteriye gider; insan onayi yoktur.

Kurallar:
- intent: olumlu | soru | olumsuz | spam | itiraz
- olumlu / soru: reply_text uretirken ornek template'i ANCHOR olarak kullan.
  Tonu, uzunlugu, emoji kullanim stilini KOPYALA. Tekrar olmasin diye
  cumlelerde kucuk varyasyonlar yap.
- itiraz: musteri fiyat/rekabet/erteleme/olcek/teknoloji/kanit itirazi
  yapiyorsa intent=itiraz. objection_type'i bu tiplerden biri olarak SEC.
  reply_text'i ITIRAZ OYUN KITABI'ndaki eslesen anchor'i baz alarak yaz.
- ANCHOR'daki gercek bilgileri AYNEN KORU — halusine edilemez:
    * "Bodrumdayim", "Marmaris", "Fethiye yoluna cikiyorum"
    * "30 dakikalik gorusme", "yuz yuze", "kahve"
    * "Booking komisyonu odemeden direkt rezervasyon"
- ONCEKI KONUSMA verildiyse:
  * Musteriyi taniyormus gibi davran; ilk defa karsilasmis havasina girme.
  * Daha once soyledigin SOZU TEKRAR ETME ("Bodrumdayim" zaten dediysen tekrar
    deme, sadece gerektiginde an).
  * Yeni gelen mesajdaki NOKTAYA odaklan; konuyu degistirme.
  * Ton ve hitap sekli onceki giden mesajlarinla TUTARLI olsun.
- olumsuz / spam: reply_text BOS birak.
- Link yok, fiyat yok, garanti yok. Sadece bir sonraki adim (gorusme talebi).
- Anchor template'te emoji varsa kopyala; yoksa ekleme.
- confidence: siniflandirmadan ne kadar emin oldugun (0-1). Belirsiz
  mesajlarda dusuk skor ver -> yanit gonderilmez.
"""


def _format_playbook(playbook: dict[str, list[str]] | None) -> str | None:
    if not playbook:
        return None
    lines: list[str] = []
    for obj_type, anchors in playbook.items():
        if anchors:
            lines.append(f"[{obj_type}] {anchors[0]}")
    return "\n\n".join(lines) if lines else None


def _format_history(history: list[dict[str, Any]] | None) -> str | None:
    """Onceki konusmayi LLM icin kompakt formatta render et (eski->yeni)."""
    if not history:
        return None
    lines: list[str] = []
    for row in history:
        yon = row.get("yon") or "?"
        tur = row.get("tur") or "-"
        tarih = (row.get("tarih") or "")[:10]  # YYYY-MM-DD
        body = (row.get("mesaj_icerigi") or "").strip()
        if not body:
            continue
        # Cok uzun mesajlari kirp
        if len(body) > 280:
            body = body[:280] + "…"
        lines.append(f"[{yon} {tur} {tarih}] {body}")
    return "\n".join(lines) if lines else None


def _build_user_prompt(
    message: str,
    intent_guess: str | None,
    base_template: str | None,
    *,
    playbook: dict[str, list[str]] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        "Gelen mesaj:",
        f'"""{message.strip()}"""',
    ]
    history_text = _format_history(history)
    if history_text:
        lines.append("")
        lines.append("ONCEKI KONUSMA (eski -> yeni):")
        lines.append(f'"""{history_text}"""')
    if base_template:
        lines.append("")
        lines.append("Ornek ton / yapidaki sablon:")
        lines.append(f'"""{base_template}"""')
    playbook_text = _format_playbook(playbook)
    if playbook_text:
        lines.append("")
        lines.append(
            "ITIRAZ OYUN KITABI (intent=itiraz ise eslesen tipi anchor al):"
        )
        lines.append(f'"""{playbook_text}"""')
    if intent_guess:
        lines.append("")
        lines.append(f"Ilk izlenim niyet: {intent_guess}")
    return "\n".join(lines)


def _pick_base_template(
    templates: dict[str, list[str]] | None,
    intent_guess: str | None,
    rng: random.Random | None = None,
) -> str | None:
    rng = rng or random
    pool: list[str] = []
    if templates and intent_guess:
        pool = templates.get(intent_guess) or []
    if not pool:
        pool = FALLBACK_TEMPLATES.get("olumlu") or []
    return rng.choice(pool) if pool else None


def _create_agent(model: str) -> Agent:
    return Agent(
        name="auto_reply_responder",
        instructions=_INSTRUCTIONS,
        output_type=AutoReplyDecision,
        model=model,
    )


async def decide_reply(
    message: str,
    *,
    config: AutoReplyConfig | None = None,
    intent_guess: str | None = None,
    templates: dict[str, list[str]] | None = None,
    rng: random.Random | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> AutoReplyDecision:
    """Classify + draft a reply. Pure function over (message, templates, history)."""
    config = config or AutoReplyConfig.from_env()
    templates = templates or FALLBACK_TEMPLATES
    base = _pick_base_template(templates, intent_guess, rng=rng)
    prompt = _build_user_prompt(
        message,
        intent_guess,
        base,
        playbook=ITIRAZ_PLAYBOOK,
        history=conversation_history,
    )
    agent = _create_agent(config.model)
    result = await Runner.run(starting_agent=agent, input=prompt)
    return result.final_output


__all__ = ["AutoReplyDecision", "Intent", "ObjectionType", "decide_reply"]
