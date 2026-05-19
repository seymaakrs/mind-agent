"""LLM-driven intent classification + reply rephrase.

Tek bir OpenAI Agents SDK call. Pydantic structured output:

    AutoReplyDecision(intent, reply_text, confidence, objection_type)

intent in {"olumlu", "olumsuz", "soru", "spam", "itiraz"}.

olumlu/soru: reply_text doludur, musteriye gonderilir (runner should_send).
olumsuz/spam: reply_text bos, yanit yok.
itiraz (Faz 1): reply_text artik bir ONERI TASLAGI olarak doldurulur ve
``objection_type`` siniflandirilir. Bu taslak musteriye OTOMATIK GITMEZ —
runner sadece olumlu/soru'da gonderir; itiraz taslagi Seyma onayina dusen
oneri olarak loglanir/iletilir.

LLM gets the inbound message PLUS a randomly-sampled base template from
``FALLBACK_TEMPLATES`` (or NocoDB message_templates) for the matching
intent so its rephrase stays on-brand. Itiraz icin ek olarak
``ITIRAZ_PLAYBOOK`` anchor ozeti prompt'a eklenir.
"""
from __future__ import annotations

import random
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel, Field

from .policy import AutoReplyConfig
from .templates import FALLBACK_TEMPLATES, ITIRAZ_PLAYBOOK


Intent = Literal["olumlu", "olumsuz", "soru", "spam", "itiraz"]
ObjectionType = Literal[
    "fiyat", "rekabet", "erteleme", "olcek", "teknoloji", "kanit"
]


class AutoReplyDecision(BaseModel):
    """Structured output for the auto-reply LLM call."""

    intent: Intent = Field(
        description="Inbound mesajin niyeti. olumlu=ilgi var, soru=bilgi "
        "soruyor, olumsuz=red/iptal, spam=alakasiz, itiraz=fiyat/rekabet/"
        "kanit/erteleme/olcek/teknoloji itirazi."
    )
    reply_text: str = Field(
        default="",
        description="TR yanit. olumlu/soru: musteriye gidecek yanit. "
        "itiraz: Seyma onayina dusen ONERI taslagi (otomatik gitmez). "
        "olumsuz/spam: BOS birak.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Siniflandirma guven skoru 0-1.",
    )
    objection_type: ObjectionType | None = Field(
        default=None,
        description="Sadece intent=itiraz iken doldur: itirazin tipi "
        "(fiyat/rekabet/erteleme/olcek/teknoloji/kanit). Diger intent'lerde "
        "None birak.",
    )


_INSTRUCTIONS = """\
Sen Slowdays satis ekibinin WhatsApp asistanisin. Otel sahiplerinden gelen
inbound mesajlari okur, niyetini siniflandirir ve KISA, SAMIMI, TR bir yanit
yazarsin.

Kurallar:
- intent: olumlu | soru | olumsuz | spam | itiraz
- olumlu / soru: reply_text uretirken ornek template'i ANCHOR olarak kullan.
  Tonu, uzunlugu, emoji kullanim stilini KOPYALA. Tekrar olmasin diye
  cumlelerde kucuk varyasyonlar yap.
- itiraz: musteri fiyat/rekabet/erteleme/olcek/teknoloji/kanit itirazi
  yapiyorsa intent=itiraz. objection_type'i bu tiplerden biri olarak SEC.
  reply_text'i, asagidaki ITIRAZ OYUN KITABI'ndaki ESLESEN anchor'i baz
  alarak yaz — bu bir ONERI taslagidir, musteriye otomatik gitmez, Seyma
  onaylar. Anchor'in tonunu/uzunlugunu KOPYALA, mesaja gore kucuk
  varyasyon yap.
- ANCHOR'daki gercek bilgileri AYNEN KORU — bu detaylar halusine edilemez:
    * "Bodrumdayim", "Marmaris", "Fethiye yoluna cikiyorum"
    * "30 dakikalik gorusme", "yuz yuze", "kahve"
    * "Booking komisyonu odemeden direkt rezervasyon"
  Bu bilgiler Slowdays satis ekibinin gercek sahadaki durumunu yansitir.
- olumsuz / spam: reply_text BOS birak (yanit verilmeyecek).
- Link yok, fiyat yok, garanti yok. Sadece bir sonraki adim (gorusme talebi).
- Anchor template'te emoji varsa kopyala; yoksa ekleme.
- confidence: siniflandirmadan ne kadar emin oldugun (0-1). Belirsiz
  mesajlarda dusuk skor ver -> insan ele alir.
"""


def _format_playbook(playbook: dict[str, list[str]] | None) -> str | None:
    """Compact one-anchor-per-objection summary for the prompt."""
    if not playbook:
        return None
    lines: list[str] = []
    for obj_type, anchors in playbook.items():
        if anchors:
            lines.append(f"[{obj_type}] {anchors[0]}")
    return "\n\n".join(lines) if lines else None


def _build_user_prompt(
    message: str,
    intent_guess: str | None,
    base_template: str | None,
    *,
    playbook: dict[str, list[str]] | None = None,
) -> str:
    lines = [
        "Gelen mesaj:",
        f'"""{message.strip()}"""',
    ]
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
    """Pick a random base template for the LLM to anchor its rephrase."""
    rng = rng or random
    pool: list[str] = []
    if templates and intent_guess:
        pool = templates.get(intent_guess) or []
    if not pool:
        # Fall back to the broadest reservoir (olumlu) so the model has SOME
        # anchor even when we don't yet know the intent.
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
) -> AutoReplyDecision:
    """Classify + draft a reply. Pure function over (message, templates)."""
    config = config or AutoReplyConfig.from_env()
    templates = templates or FALLBACK_TEMPLATES
    base = _pick_base_template(templates, intent_guess, rng=rng)
    prompt = _build_user_prompt(
        message, intent_guess, base, playbook=ITIRAZ_PLAYBOOK
    )
    agent = _create_agent(config.model)
    result = await Runner.run(starting_agent=agent, input=prompt)
    return result.final_output


__all__ = ["AutoReplyDecision", "Intent", "ObjectionType", "decide_reply"]
