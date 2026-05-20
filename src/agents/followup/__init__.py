"""Follow-up Agent — cevapsiz soguk leadlere kibar takip mesaji atar.

Outreach 3 gun once mesaj atti ama lead cevap vermediyse (asama=Soguk ve
Gelen mesaj yok), follow-up agent Meta-onayli takip template'i gonderir.
Guardian outreach_paused bayragini paylasir — sistem bozuksa o da durur.

Modul:
- policy.py    FollowupConfig + FollowupPolicy (saat penceresi, gunluk limit)
- targeting.py find_followup_targets, count_sent_today
- runner.py    Cloud Run job entry-point, send_one, main loop
"""
from __future__ import annotations

from src.agents.followup.policy import FollowupConfig, FollowupPolicy
from src.agents.followup.targeting import (
    count_sent_today,
    find_followup_targets,
)

__all__ = [
    "FollowupConfig",
    "FollowupPolicy",
    "count_sent_today",
    "find_followup_targets",
]
