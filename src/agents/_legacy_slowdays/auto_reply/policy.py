"""Auto-reply pacing & config (env-driven).

Seyma'nin ``lead_monitor.py``: 60sn polling, 30-60sn reply gecikmesi.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoReplyConfig:
    poll_interval_sec: int = 60
    reply_min_delay_sec: int = 30
    reply_max_delay_sec: int = 60
    batch_size: int = 10  # one poll handles up to N inbounds
    max_inbound_age_minutes: int = 60  # skip if older (likely missed window)
    model: str = "gpt-4o-mini"
    daily_cap: int = 100  # 0 = unlimited (cap disabled)
    business_id: str = ""  # empty = no brand injection
    enable_brand_aware: bool = True

    @classmethod
    def from_env(cls) -> "AutoReplyConfig":
        def _int(name: str, default: int) -> int:
            v = os.environ.get(name)
            try:
                return int(v) if v else default
            except ValueError:
                return default

        def _bool(name: str, default: bool) -> bool:
            v = os.environ.get(name)
            if v is None:
                return default
            return v.strip().lower() in ("1", "true", "yes")

        return cls(
            poll_interval_sec=_int("AUTO_REPLY_POLL_SEC", cls.poll_interval_sec),
            reply_min_delay_sec=_int("AUTO_REPLY_MIN_DELAY_SEC", cls.reply_min_delay_sec),
            reply_max_delay_sec=_int("AUTO_REPLY_MAX_DELAY_SEC", cls.reply_max_delay_sec),
            batch_size=_int("AUTO_REPLY_BATCH_SIZE", cls.batch_size),
            max_inbound_age_minutes=_int(
                "AUTO_REPLY_MAX_AGE_MIN", cls.max_inbound_age_minutes
            ),
            model=os.environ.get("AUTO_REPLY_MODEL", cls.model),
            daily_cap=_int("AUTO_REPLY_DAILY_CAP", cls.daily_cap),
            business_id=os.environ.get("AUTO_REPLY_BUSINESS_ID", cls.business_id),
            enable_brand_aware=_bool(
                "AUTO_REPLY_BRAND_AWARE", cls.enable_brand_aware
            ),
        )

    def jitter_delay(self, rng: random.Random | None = None) -> float:
        rng = rng or random
        return rng.uniform(self.reply_min_delay_sec, self.reply_max_delay_sec)
