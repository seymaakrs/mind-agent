"""Guardian thresholds + cadence (env-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardianConfig:
    """Esikler ve polling sikligi.

    Notlar:
    - reply_rate sayisal degerleri yuzde olarak (5.0 = %5).
    - min_outreach_for_eval: az gonderim yapildiysa rate yorum disi (kucuk
      orneklem yaniltici). Default 50 — ilk 50 mesajdan sonra Bekci karar
      verir.
    """

    poll_interval_sec: int = 1800  # 30dk
    window_hours: int = 24

    # Reply Rate esikleri
    reply_rate_yellow_pct: float = 5.0   # alti -> uyari
    reply_rate_red_pct: float = 3.0      # alti -> PAUSE

    # Engagement Rate (auto-reply'in cevap verme orani — dusukse intent
    # classifier'in cogu mesajda 'olumsuz/spam' dedigini gosterir).
    engagement_rate_yellow_pct: float = 40.0  # alti -> uyari
    engagement_rate_red_pct: float = 20.0     # alti -> PAUSE

    # Outreach failure rate (FAILED status — Zernio block/timeout). Adim 9'da
    # Outreach runner FAILED log'u Etkilesimler'e yazacak. Simdilik kullanilmaz.
    failure_rate_yellow_pct: float = 5.0
    failure_rate_red_pct: float = 10.0

    # Minimum gonderim sayisi: bunun altinda hicbir kararı verilmez (kucuk
    # orneklem). Sabah ilk 50 mesaja kadar Bekci sessiz.
    min_outreach_for_eval: int = 50

    @classmethod
    def from_env(cls) -> "GuardianConfig":
        def _int(name: str, default: int) -> int:
            v = os.environ.get(name)
            try:
                return int(v) if v else default
            except ValueError:
                return default

        def _float(name: str, default: float) -> float:
            v = os.environ.get(name)
            try:
                return float(v) if v else default
            except ValueError:
                return default

        return cls(
            poll_interval_sec=_int("GUARDIAN_POLL_SEC", cls.poll_interval_sec),
            window_hours=_int("GUARDIAN_WINDOW_HOURS", cls.window_hours),
            reply_rate_yellow_pct=_float(
                "GUARDIAN_REPLY_YELLOW", cls.reply_rate_yellow_pct
            ),
            reply_rate_red_pct=_float(
                "GUARDIAN_REPLY_RED", cls.reply_rate_red_pct
            ),
            engagement_rate_yellow_pct=_float(
                "GUARDIAN_ENGAGEMENT_YELLOW", cls.engagement_rate_yellow_pct
            ),
            engagement_rate_red_pct=_float(
                "GUARDIAN_ENGAGEMENT_RED", cls.engagement_rate_red_pct
            ),
            failure_rate_yellow_pct=_float(
                "GUARDIAN_FAILURE_YELLOW", cls.failure_rate_yellow_pct
            ),
            failure_rate_red_pct=_float(
                "GUARDIAN_FAILURE_RED", cls.failure_rate_red_pct
            ),
            min_outreach_for_eval=_int(
                "GUARDIAN_MIN_OUTREACH", cls.min_outreach_for_eval
            ),
        )
