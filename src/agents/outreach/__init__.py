"""Outreach Agent — Cloud Run job that sends cold WhatsApp templates 24/7.

Replaces Seyma's local ``otel_gonderim.py`` Windows script:

- ``policy.py``    business hours, daily limit, batch break, jitter delay
- ``targeting.py`` pick the next NocoDB lead eligible for outreach
- ``runner.py``    main loop (long-running Cloud Run job entry-point)

Triggered as a long-running worker (Cloud Run job, sleep loop). Cron is
intentionally NOT used so the natural rate-limit is preserved (jitter +
batch breaks emulate human pacing). Image is the same mind-agent container,
just a different command:

    python -m src.agents.outreach.runner
"""
from __future__ import annotations

from .policy import OutreachPolicy, OutreachConfig
from .targeting import pick_next_target


__all__ = ["OutreachPolicy", "OutreachConfig", "pick_next_target"]
