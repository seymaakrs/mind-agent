"""State machine: GuardianMetrics + GuardianConfig -> Decision.

Pure function (no I/O) so test'ler hizli ve net. Runner bu kararı alip
NocoDB'ye yazar / mail tetikler.

Kapali dongu (sessiz ucluyu canlandirma):
- RED  -> outreach PAUSE (pause_outreach=True)
- GREEN -> outreach otomatik RESUME (resume_outreach=True). Insan onayi
  YOK; metrikler toparlayinca Bekci kendisi yeniden baslatir.
- YELLOW / INSUFFICIENT -> aksiyon yok (belirsiz; mevcut durum korunur).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .metrics import GuardianMetrics
from .policy import GuardianConfig


class DecisionLevel(str, Enum):
    GREEN = "GREEN"      # her sey yolunda
    YELLOW = "YELLOW"    # uyari, devam
    RED = "RED"          # PAUSE outreach
    INSUFFICIENT = "INSUFFICIENT"  # min_outreach altinda, karar verme


# recommended_action degerleri
ACTION_PAUSE = "PAUSE"
ACTION_RESUME = "RESUME"
ACTION_NONE = "NONE"


@dataclass
class Decision:
    level: DecisionLevel
    reasons: list[str] = field(default_factory=list)
    pause_outreach: bool = False
    resume_outreach: bool = False
    recommended_action: str = ACTION_NONE

    def reason_summary(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "all green"


def decide(metrics: GuardianMetrics, config: GuardianConfig) -> Decision:
    """Karari ver: GREEN / YELLOW / RED / INSUFFICIENT (+ otomatik resume)."""
    if metrics.outreach_sent < config.min_outreach_for_eval:
        return Decision(
            level=DecisionLevel.INSUFFICIENT,
            reasons=[
                f"only {metrics.outreach_sent} outreach in last {metrics.window_hours}h "
                f"(min for eval: {config.min_outreach_for_eval})"
            ],
        )

    reasons: list[str] = []
    level = DecisionLevel.GREEN

    # Reply rate kontrolu
    if metrics.reply_rate_pct < config.reply_rate_red_pct:
        reasons.append(
            f"reply_rate {metrics.reply_rate_pct}% < red esik "
            f"{config.reply_rate_red_pct}% (kotu template / yanlis hedef)"
        )
        level = DecisionLevel.RED
    elif metrics.reply_rate_pct < config.reply_rate_yellow_pct:
        reasons.append(
            f"reply_rate {metrics.reply_rate_pct}% < yellow esik "
            f"{config.reply_rate_yellow_pct}%"
        )
        level = _max_level(level, DecisionLevel.YELLOW)

    # Engagement rate (auto-reply'in karar verdigi) — sadece inbound varsa
    if metrics.inbound_received >= 5:  # az inbound'da bu rate yaniltici
        if metrics.engagement_rate_pct < config.engagement_rate_red_pct:
            reasons.append(
                f"engagement_rate {metrics.engagement_rate_pct}% < red "
                f"{config.engagement_rate_red_pct}% (cogu inbound olumsuz/spam — "
                "muhtemelen yanlis hedef segment)"
            )
            level = DecisionLevel.RED
        elif metrics.engagement_rate_pct < config.engagement_rate_yellow_pct:
            reasons.append(
                f"engagement_rate {metrics.engagement_rate_pct}% < yellow "
                f"{config.engagement_rate_yellow_pct}%"
            )
            level = _max_level(level, DecisionLevel.YELLOW)

    # Failure rate (Adim 9 ile aktif olacak)
    if metrics.failure_rate_pct >= config.failure_rate_red_pct:
        reasons.append(
            f"failure_rate {metrics.failure_rate_pct}% >= red "
            f"{config.failure_rate_red_pct}% (Zernio block/timeout — ban riski)"
        )
        level = DecisionLevel.RED
    elif metrics.failure_rate_pct >= config.failure_rate_yellow_pct:
        reasons.append(
            f"failure_rate {metrics.failure_rate_pct}% >= yellow "
            f"{config.failure_rate_yellow_pct}%"
        )
        level = _max_level(level, DecisionLevel.YELLOW)

    pause = level == DecisionLevel.RED
    # GREEN = net toparlama. Daha once PAUSE edilmis olabilir; Bekci insan
    # onayi beklemeden outreach'i kendi yeniden baslatir (idempotent: zaten
    # acikken tekrar False yazmak zararsiz). YELLOW belirsiz — resume yok.
    resume = level == DecisionLevel.GREEN

    if pause:
        action = ACTION_PAUSE
    elif resume:
        action = ACTION_RESUME
    else:
        action = ACTION_NONE

    return Decision(
        level=level,
        reasons=reasons,
        pause_outreach=pause,
        resume_outreach=resume,
        recommended_action=action,
    )


_LEVEL_ORDER = {
    DecisionLevel.GREEN: 0,
    DecisionLevel.YELLOW: 1,
    DecisionLevel.RED: 2,
    DecisionLevel.INSUFFICIENT: 0,
}


def _max_level(a: DecisionLevel, b: DecisionLevel) -> DecisionLevel:
    return a if _LEVEL_ORDER[a] >= _LEVEL_ORDER[b] else b
