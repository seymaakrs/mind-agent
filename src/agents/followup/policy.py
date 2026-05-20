"""Follow-up pacing & eligibility — outreach'tan slim ve daha temkinli.

Outreach 240/gun atarken follow-up 80/gun atar (ek WhatsApp yuku). Saat
penceresi outreach'tan biraz dar; jitter araligı daha genis (ban riski en
yuksek burada cunku ayni numaraya 2. mesaj).
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class FollowupConfig:
    timezone: str = "Europe/Istanbul"
    hour_start: int = 10              # outreach 9'da basliyor; follow-up 10'da
    hour_end: int = 20                # erken bit
    daily_limit: int = 80             # outreach'tan dusuk
    min_delay_sec: int = 60           # outreach 25-90; follow-up 60-180 daha temkinli
    max_delay_sec: int = 180
    batch_size: int = 10              # 10'da bir uzun mola
    batch_break_min_sec: int = 300
    batch_break_max_sec: int = 600
    days_since_outreach: int = 3      # son_temas N gun once
    # Meta-onayli takip template'i. Seyma'nin Business Manager'da yeni
    # template olarak onaylatmasi gerekir (deploy notlarinda detay).
    template_name: str = "ege_otel_takip_v1"
    template_language: str = "tr"
    source_workflow_id: str = "outreach_agent_v1"

    @classmethod
    def from_env(cls) -> "FollowupConfig":
        def _int(name: str, default: int) -> int:
            v = os.environ.get(name)
            try:
                return int(v) if v else default
            except ValueError:
                return default

        return cls(
            timezone=os.environ.get("FOLLOWUP_TZ", cls.timezone),
            hour_start=_int("FOLLOWUP_HOUR_START", cls.hour_start),
            hour_end=_int("FOLLOWUP_HOUR_END", cls.hour_end),
            daily_limit=_int("FOLLOWUP_DAILY_LIMIT", cls.daily_limit),
            min_delay_sec=_int("FOLLOWUP_MIN_DELAY_SEC", cls.min_delay_sec),
            max_delay_sec=_int("FOLLOWUP_MAX_DELAY_SEC", cls.max_delay_sec),
            batch_size=_int("FOLLOWUP_BATCH_SIZE", cls.batch_size),
            batch_break_min_sec=_int(
                "FOLLOWUP_BATCH_BREAK_MIN_SEC", cls.batch_break_min_sec
            ),
            batch_break_max_sec=_int(
                "FOLLOWUP_BATCH_BREAK_MAX_SEC", cls.batch_break_max_sec
            ),
            days_since_outreach=_int(
                "FOLLOWUP_DAYS", cls.days_since_outreach
            ),
            template_name=os.environ.get(
                "FOLLOWUP_TEMPLATE_NAME", cls.template_name
            ),
            template_language=os.environ.get(
                "FOLLOWUP_TEMPLATE_LANGUAGE", cls.template_language
            ),
            source_workflow_id=os.environ.get(
                "FOLLOWUP_SOURCE_WORKFLOW_ID", cls.source_workflow_id
            ),
        )


class FollowupPolicy:
    def __init__(self, config: FollowupConfig | None = None) -> None:
        self.config = config or FollowupConfig.from_env()
        self.sent_today = 0
        self._batch_in_progress = 0

    def within_business_hours(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        local = now.astimezone(ZoneInfo(self.config.timezone))
        return self.config.hour_start <= local.hour < self.config.hour_end

    def under_daily_limit(self) -> bool:
        return self.sent_today < self.config.daily_limit

    def is_eligible(self, now: datetime | None = None) -> tuple[bool, str]:
        if not self.within_business_hours(now):
            return False, "outside business hours"
        if not self.under_daily_limit():
            return False, "daily limit reached"
        return True, "ok"

    def next_delay_sec(self, rng: random.Random | None = None) -> float:
        rng = rng or random
        return rng.uniform(self.config.min_delay_sec, self.config.max_delay_sec)

    def batch_break_sec(self, rng: random.Random | None = None) -> float:
        rng = rng or random
        return rng.uniform(
            self.config.batch_break_min_sec, self.config.batch_break_max_sec
        )

    def should_take_batch_break(self) -> bool:
        return (
            self._batch_in_progress > 0
            and self._batch_in_progress % self.config.batch_size == 0
        )

    def record_send(self) -> None:
        self.sent_today += 1
        self._batch_in_progress += 1

    def reset_daily(self) -> None:
        self.sent_today = 0
