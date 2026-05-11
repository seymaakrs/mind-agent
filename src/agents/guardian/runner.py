"""Guardian (Bekci) main loop — Cloud Run job entry-point.

    python -m src.agents.guardian.runner

Her tick:
1. Etkilesimler'den 24h metric'lerini hesapla
2. decide() ile karar al
3. NocoDB system_settings tablosuna yaz (single-row pattern):
   - last_metrics_json
   - last_health_check
   - level (GREEN/YELLOW/RED)
   - reason_summary
   - pause_outreach=True ise: outreach_paused=True + pause_reason + paused_at
4. Mail icin n8n "Bekci Alert" webhook'una POST (env: GUARDIAN_ALERT_WEBHOOK_URL)
   — yoksa sadece log.

NOT: Outreach Robotu her tick basinda system_settings.outreach_paused'i
kontrol eder (ayri PR — runner.py guncellenir).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from src.agents.guardian.decisions import Decision, DecisionLevel, decide
from src.agents.guardian.metrics import compute_metrics
from src.agents.guardian.policy import GuardianConfig
from src.app.config import get_settings
from src.infra.nocodb_client import get_nocodb_client


log = logging.getLogger("guardian")

_PAUSE_ERROR_SEC = 60


def _settings_table_id() -> str | None:
    return os.environ.get("NOCODB_SETTINGS_TABLE_ID") or None


def _alert_webhook_url() -> str | None:
    return os.environ.get("GUARDIAN_ALERT_WEBHOOK_URL") or None


async def _send_alert_webhook(payload: dict[str, Any]) -> None:
    """Best-effort POST to n8n Bekci Alert workflow. Mail/Slack delegated there."""
    url = _alert_webhook_url()
    if not url:
        log.info("guardian: no alert webhook configured (GUARDIAN_ALERT_WEBHOOK_URL)")
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json=payload)
    except Exception as exc:
        log.warning("guardian: alert webhook failed: %s", exc)


def _persist_health_check(
    settings_tbl: str,
    *,
    metrics_dict: dict[str, Any],
    decision: Decision,
    timestamp: str,
) -> None:
    """Single-row update on system_settings (Id=1 by convention)."""
    nocodb = get_nocodb_client()
    fields: dict[str, Any] = {
        "last_health_check": timestamp,
        "last_metrics_json": json.dumps(metrics_dict, ensure_ascii=False),
        "last_decision_level": decision.level.value,
        "last_decision_reason": decision.reason_summary(),
    }
    if decision.pause_outreach:
        fields["outreach_paused"] = True
        fields["pause_reason"] = decision.reason_summary()
        fields["paused_at"] = timestamp
    try:
        nocodb.update_record(settings_tbl, 1, fields)
    except Exception as exc:
        log.warning("guardian: failed to persist health check: %s", exc)


async def tick(config: GuardianConfig) -> dict[str, Any]:
    """Tek bir health check turu. Test'lerden de cagrilabilir."""
    app_settings = get_settings()
    msgs_tbl = app_settings.nocodb_messages_table_id
    settings_tbl = _settings_table_id()

    if not msgs_tbl:
        log.error("guardian: NOCODB_MESSAGES_TABLE_ID missing — skipping")
        return {"ok": False, "reason": "messages_table missing"}

    metrics = compute_metrics(
        get_nocodb_client(), msgs_tbl, window_hours=config.window_hours
    )
    decision = decide(metrics, config)
    timestamp = datetime.now(timezone.utc).isoformat()

    log.info(
        "guardian: level=%s reply=%.2f%% engagement=%.2f%% failure=%.2f%% (out=%d, in=%d, auto=%d) — %s",
        decision.level.value,
        metrics.reply_rate_pct,
        metrics.engagement_rate_pct,
        metrics.failure_rate_pct,
        metrics.outreach_sent,
        metrics.inbound_received,
        metrics.auto_replies_sent,
        decision.reason_summary(),
    )

    if settings_tbl:
        _persist_health_check(
            settings_tbl,
            metrics_dict=metrics.to_dict(),
            decision=decision,
            timestamp=timestamp,
        )
    else:
        log.warning(
            "guardian: NOCODB_SETTINGS_TABLE_ID not set — pause flag CANNOT be "
            "persisted; Outreach won't see it. Set it before going live."
        )

    if decision.level in (DecisionLevel.YELLOW, DecisionLevel.RED):
        await _send_alert_webhook({
            "level": decision.level.value,
            "reason": decision.reason_summary(),
            "metrics": metrics.to_dict(),
            "timestamp": timestamp,
            "pause_outreach": decision.pause_outreach,
        })

    return {
        "ok": True,
        "level": decision.level.value,
        "metrics": metrics.to_dict(),
        "reason": decision.reason_summary(),
    }


async def loop(
    config: GuardianConfig | None = None, *, max_iterations: int | None = None
) -> None:
    config = config or GuardianConfig.from_env()
    log.info(
        "guardian starting: window=%dh poll=%ds reply_thresholds=%.1f/%.1f%% "
        "engagement_thresholds=%.1f/%.1f%% min_outreach=%d",
        config.window_hours,
        config.poll_interval_sec,
        config.reply_rate_yellow_pct,
        config.reply_rate_red_pct,
        config.engagement_rate_yellow_pct,
        config.engagement_rate_red_pct,
        config.min_outreach_for_eval,
    )
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            await tick(config)
            await asyncio.sleep(config.poll_interval_sec)
        except Exception as exc:
            log.exception("guardian: tick failed: %s", exc)
            await asyncio.sleep(_PAUSE_ERROR_SEC)


def _install_sigterm_handler() -> None:
    def _stop(*_: object) -> None:
        log.info("guardian: SIGTERM received")

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
        pass


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _install_sigterm_handler()
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
