"""State machine: GuardianMetrics + GuardianConfig -> Decision.

Pure function (no I/O) so test'ler hizli ve net. Runner bu kararı alip
NocoDB'ye yazar / mail tetikler.
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


@dataclass
class Decision:
    level: DecisionLevel
    reasons: list[str] = field(default_factory=list)
    pause_outreach: bool = False

    def reason_summary(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "all green"


def decide(metrics: GuardianMetrics, config: GuardianConfig) -> Decision:
    """Karari ver: GREEN / YELLOW / RED / INSUFFICIENT."""
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

    return Decision(
        level=level,
        reasons=reasons,
        pause_outreach=(level == DecisionLevel.RED),
    )


_LEVEL_ORDER = {
    DecisionLevel.GREEN: 0,
    DecisionLevel.YELLOW: 1,
    DecisionLevel.RED: 2,
    DecisionLevel.INSUFFICIENT: 0,
}


def _max_level(a: DecisionLevel, b: DecisionLevel) -> DecisionLevel:
    return a if _LEVEL_ORDER[a] >= _LEVEL_ORDER[b] else b
