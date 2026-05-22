"""LLM intent classifier for inbound Instagram comments.

Mirrors ``src/agents/auto_reply/responder.py``'s pattern: a single OpenAI
Agents SDK call with Pydantic structured output. Categories:

    pricing_question / availability_question / compliment /
    complaint / spam / other
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CommentIntent = Literal[
    "pricing_question",
    "availability_question",
    "compliment",
    "complaint",
    "spam",
    "other",
]


class CommentClassification(BaseModel):
    intent: CommentIntent = Field(
        description=(
            "pricing_question=fiyat/ucret sorusu, availability_question="
            "musait mi/rezervasyon sorusu, compliment=ovgu/begeni, "
            "complaint=sikayet/red, spam=alakasiz/reklam, other=diger."
        )
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Tek cumle gerekce.")


_INSTRUCTIONS = """\
Instagram yorumlarini siniflandiran asistansin. Cikti SADECE structured
output (CommentClassification). Kategoriler:
- pricing_question: "ne kadar", "fiyat", "ucret", "kac TL/USD"
- availability_question: "musait mi", "rezervasyon", "stok var mi",
  "ne zaman acik"
- compliment: "harika", "cok guzel", begeni emoji'leri
- complaint: "kotu", "iade", "sikayet"
- spam: link, alakasiz reklam, takipci satin alma onerileri
- other: yukaridakilerin disindaki her sey, anlasilmayan kisa metin

confidence: 0.0-1.0 arasi. Belirsizse 0.5'in altinda ver.
"""


async def classify_comment(
    text: str,
    *,
    model: str = "gpt-4o-mini",
) -> CommentClassification:
    """Run the classifier. Returns ``CommentClassification``.

    Defensive: empty text → ``other`` with confidence 0.0 (no LLM call).
    """
    if not (text or "").strip():
        return CommentClassification(intent="other", confidence=0.0, reasoning="empty text")
    # Lazy import — keeps module import cheap for tests that monkeypatch this.
    from agents import Agent, Runner

    agent = Agent(
        name="CommentClassifier",
        instructions=_INSTRUCTIONS,
        model=model,
        output_type=CommentClassification,
    )
    result = await Runner.run(agent, input=text)
    out = result.final_output
    if isinstance(out, CommentClassification):
        return out
    return CommentClassification(intent="other", confidence=0.0, reasoning="parse fallback")


__all__ = ["CommentClassification", "CommentIntent", "classify_comment"]
