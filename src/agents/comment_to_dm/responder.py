"""Decision matrix + DM body composition for Comment-to-DM."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.agents.comment_to_dm.classifier import CommentClassification
from src.agents.comment_to_dm.policy import CommentToDMConfig


Action = Literal["dm", "like_and_dm", "notify_seyma", "tag_spam", "ignore"]


@dataclass
class CommentDecision:
    action: Action
    reason: str
    dm_text: str = ""
    confidence: float = 0.0


_PRICING_TEMPLATE_DEFAULT = (
    "Merhaba! Yorumunuz icin tesekkurler. Fiyat detaylari ve musait "
    "tarihler icin DM'den size yazabilirim — kisa bir bilgi yeterli."
)
_AVAILABILITY_TEMPLATE_DEFAULT = (
    "Selam! Musaitlik durumumuz icin DM'den size ozel takvim "
    "paylasabilirim. Hangi tarihler size uygun?"
)
_THANK_YOU_TEMPLATE = (
    "Cok tesekkur ederim guzel yorumunuz icin! Sizi de aramizda gormek "
    "harika."
)


def decide(
    classification: CommentClassification,
    cfg: CommentToDMConfig,
    *,
    min_confidence: float = 0.5,
) -> CommentDecision:
    """Map (intent, config) → action. Pure function — easy to test."""
    intent = classification.intent
    conf = classification.confidence
    if intent in ("pricing_question", "availability_question") and conf >= min_confidence:
        body = cfg.pricing_template or (
            _PRICING_TEMPLATE_DEFAULT
            if intent == "pricing_question"
            else _AVAILABILITY_TEMPLATE_DEFAULT
        )
        return CommentDecision(
            action="dm",
            reason=f"{intent} intent",
            dm_text=body,
            confidence=conf,
        )
    if intent == "compliment":
        if cfg.thank_you_enabled and conf >= min_confidence:
            return CommentDecision(
                action="like_and_dm",
                reason="compliment + thank_you_enabled",
                dm_text=_THANK_YOU_TEMPLATE,
                confidence=conf,
            )
        return CommentDecision(action="ignore", reason="compliment but opt-out", confidence=conf)
    if intent == "complaint":
        return CommentDecision(
            action="notify_seyma",
            reason="complaint — human escalation",
            confidence=conf,
        )
    if intent == "spam":
        return CommentDecision(action="tag_spam", reason="spam classifier", confidence=conf)
    return CommentDecision(
        action="ignore",
        reason=f"intent={intent} conf={conf:.2f} below threshold",
        confidence=conf,
    )


__all__ = ["CommentDecision", "decide", "Action"]
