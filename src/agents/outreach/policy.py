"""Pacing & eligibility rules for the Outreach Agent.

Encodes Seyma's ``otel_gonderim.py`` heuristics:

- 09:00-21:00 Europe/Istanbul business hours
- 240 mesaj/24h hard cap (WhatsApp TIER_250 buffer)
- 25-90 sn jitter between sends
- 4-7 dk break every 20 messages (batch break)

Pure (no I/O) so the runner can drive the policy with synthetic clocks
in tests without freezegun-style monkey patching.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class OutreachConfig:
    """All knobs read from env at startup. Defaults match Seyma's script."""

    timezone: str = "Europe/Istanbul"
    hour_start: int = 9
    hour_end: int = 21
    daily_limit: int = 240
    min_delay_sec: int = 25
    max_delay_sec: int = 90
    batch_size: int = 20
    batch_break_min_sec: int = 240
    batch_break_max_sec: int = 420
    template_name: str = "ege_otel_yaz_sezon_v1"
    template_language: str = "tr"
    source_workflow_id: str = "outreach_agent_v1"

    @classmethod
    def from_env(cls) -> "OutreachConfig":
        def _int(name: str, default: int) -> int:
            v = os.environ.get(name)
            try:
                return int(v) if v else default
            except ValueError:
                return default

        return cls(
            timezone=os.environ.get("OUTREACH_TZ", cls.timezone),
            hour_start=_int("OUTREACH_HOUR_START", cls.hour_start),
            hour_end=_int("OUTREACH_HOUR_END", cls.hour_end),
            daily_limit=_int("OUTREACH_DAILY_LIMIT", cls.daily_limit),
            min_delay_sec=_int("OUTREACH_MIN_DELAY_SEC", cls.min_delay_sec),
            max_delay_sec=_int("OUTREACH_MAX_DELAY_SEC", cls.max_delay_sec),
            batch_size=_int("OUTREACH_BATCH_SIZE", cls.batch_size),
            batch_break_min_sec=_int(
                "OUTREACH_BATCH_BREAK_MIN_SEC", cls.batch_break_min_sec
            ),
            batch_break_max_sec=_int(
                "OUTREACH_BATCH_BREAK_MAX_SEC", cls.batch_break_max_sec
            ),
            template_name=os.environ.get(
                "OUTREACH_TEMPLATE_NAME", cls.template_name
            ),
            template_language=os.environ.get(
                "OUTREACH_TEMPLATE_LANGUAGE", cls.template_language
            ),
            source_workflow_id=os.environ.get(
                "OUTREACH_SOURCE_WORKFLOW_ID", cls.source_workflow_id
            ),
        )


class OutreachPolicy:
    """Stateless decisions + a tiny sent counter for the running session."""

    def __init__(self, config: OutreachConfig | None = None) -> None:
        self.config = config or OutreachConfig.from_env()
        self.sent_today = 0
        self._batch_in_progress = 0

    # ---- decisions -------------------------------------------------------

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

    # ---- pacing ---------------------------------------------------------

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

    # ---- mutators -------------------------------------------------------

    def record_send(self) -> None:
        self.sent_today += 1
        self._batch_in_progress += 1

    def reset_daily(self) -> None:
        """Call at midnight (local). Keeps batch counter rolling."""
        self.sent_today = 0
