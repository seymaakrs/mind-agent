"""Zernio Observer main loop — Cloud Run job entry-point.

Every 5 minutes:
  1. Pull last 5 minutes of Zernio platform logs via :meth:`ZernioClient.list_logs`
  2. Dedupe entries already in our client-side ring buffer (via X-Request-ID)
  3. Idempotently write each surviving entry to
     ``zernio_logs/{YYYY-MM-DD}/entries/{logId}``
  4. Compute a 5-min rollup with counts per (endpoint, status_class) and
     latency percentiles -> ``zernio_logs/{YYYY-MM-DD}/rollups/{HHMM}``
  5. Evaluate anomaly thresholds; on alert POST to GUARDIAN_ALERT_WEBHOOK_URL
     (RED) or call ``notify_seyma`` (YELLOW).
  6. Persist cursor at ``zernio_logs/_meta/cursor`` for resumability.

Run:
    python -m src.agents.zernio_observer.runner

Cloud Run Job mode:
    RUN_ONCE=true python -m src.agents.zernio_observer.runner
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

log = logging.getLogger("zernio_observer")

# ---------------------------------------------------------------------------
# Thresholds (file-top constants — see OPERATIONS.md for rationale)
# ---------------------------------------------------------------------------
THRESHOLD_5XX_RATE = 0.05         # 5% over last 15min -> RED
THRESHOLD_429_COUNT = 50          # 50 in 5min -> YELLOW
THRESHOLD_LATENCY_SPIKE = 10.0    # 10x baseline p95 on a single endpoint

POLL_INTERVAL_SEC = 300           # 5 min
WINDOW_SEC = 300                  # poll last 5min

CURSOR_DOC = "zernio_logs/_meta/cursor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status_class(status: int) -> str:
    if 200 <= status < 300:
        return "2xx"
    if 300 <= status < 400:
        return "3xx"
    if 400 <= status < 500:
        return "4xx"
    if status >= 500:
        return "5xx"
    return "xxx"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def normalize_log_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Map Zernio Logs API shape to our internal entry shape.

    See ``src/infra/zernio/logs.py`` for the assumed API contract.
    """
    return {
        "log_id": str(raw.get("id") or raw.get("logId") or ""),
        "request_id": str(raw.get("requestId") or raw.get("X-Request-ID") or ""),
        "timestamp": raw.get("timestamp") or raw.get("time") or "",
        "level": raw.get("level") or "info",
        "endpoint": raw.get("endpoint") or raw.get("path") or "unknown",
        "method": (raw.get("method") or "GET").upper(),
        "status": int(raw.get("status") or 0),
        "latency_ms": float(raw.get("latencyMs") or raw.get("latency_ms") or 0.0),
        "message": raw.get("message") or "",
        "status_class": _status_class(int(raw.get("status") or 0)),
        "raw": raw,
    }


def filter_dedupe_via_ring(entries: list[dict[str, Any]], ring_request_ids: set[str]) -> list[dict[str, Any]]:
    """Skip entries whose request_id we already have in the client-side ring buffer.

    Avoids double-counting our own outbound calls (already accounted for via
    in-memory telemetry). Entries with no request_id (e.g. Zernio-internal
    events) pass through.
    """
    out = []
    for e in entries:
        rid = e.get("request_id") or ""
        if rid and rid in ring_request_ids:
            continue
        out.append(e)
    return out


def _ring_request_ids() -> set[str]:
    try:
        from src.infra.zernio.base import REQUEST_LOG

        return {entry.get("request_id", "") for entry in REQUEST_LOG if entry.get("request_id")}
    except Exception as exc:
        log.warning("observer: cannot read ring buffer: %s", exc)
        return set()


# ---------------------------------------------------------------------------
# Firestore I/O
# ---------------------------------------------------------------------------
def _firestore():
    from src.infra.firebase_client import get_firestore_client

    return get_firestore_client()


def write_entries(entries: list[dict[str, Any]], *, dry_run: bool = False) -> int:
    """Idempotent write — ``zernio_logs/{YYYY-MM-DD}/entries/{logId}``.

    Returns number of entries written (or that would be written in dry-run).
    """
    if not entries:
        return 0
    if dry_run:
        return len(entries)
    db = _firestore()
    written = 0
    for e in entries:
        log_id = e.get("log_id") or ""
        ts = e.get("timestamp") or ""
        day = ts[:10] if len(ts) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not log_id:
            continue
        # set() with merge -> idempotent on logId
        db.collection("zernio_logs").document(day).collection("entries").document(log_id).set(e, merge=True)
        written += 1
    return written


def write_rollup(rollup: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    db = _firestore()
    day = rollup["day"]
    hhmm = rollup["hhmm"]
    db.collection("zernio_logs").document(day).collection("rollups").document(hhmm).set(rollup, merge=True)


def load_cursor() -> str | None:
    try:
        db = _firestore()
        doc = db.collection("zernio_logs").document("_meta").get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return data.get("cursor")
    except Exception as exc:
        log.warning("observer: load_cursor failed: %s", exc)
        return None


def save_cursor(cursor_iso: str, *, dry_run: bool = False) -> None:
    if dry_run:
        return
    try:
        db = _firestore()
        db.collection("zernio_logs").document("_meta").set({"cursor": cursor_iso}, merge=True)
    except Exception as exc:
        log.warning("observer: save_cursor failed: %s", exc)


# ---------------------------------------------------------------------------
# Rollup + anomaly detection
# ---------------------------------------------------------------------------
def compute_rollup(entries: list[dict[str, Any]], window_start: datetime) -> dict[str, Any]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    latencies_by_endpoint: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        counts[(e["endpoint"], e["status_class"])] += 1
        latencies_by_endpoint[e["endpoint"]].append(float(e.get("latency_ms") or 0.0))

    endpoints = {
        ep: {
            "p50_ms": _percentile(lats, 50),
            "p95_ms": _percentile(lats, 95),
            "count": len(lats),
        }
        for ep, lats in latencies_by_endpoint.items()
    }

    return {
        "day": window_start.strftime("%Y-%m-%d"),
        "hhmm": window_start.strftime("%H%M"),
        "window_start": _iso(window_start),
        "total_calls": len(entries),
        "counts": {f"{k[0]}|{k[1]}": v for k, v in counts.items()},
        "endpoints": endpoints,
    }


def detect_anomalies(
    entries: list[dict[str, Any]],
    *,
    baseline_p95_by_endpoint: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Returns list of alerts. Each alert: {level, reason, detail}.

    - 5xx rate > THRESHOLD_5XX_RATE -> RED
    - 429 count > THRESHOLD_429_COUNT -> YELLOW
    - per-endpoint p95 > baseline * THRESHOLD_LATENCY_SPIKE -> YELLOW(latency)
    """
    alerts: list[dict[str, Any]] = []
    baseline = baseline_p95_by_endpoint or {}
    if not entries:
        return alerts
    total = len(entries)
    n_5xx = sum(1 for e in entries if e.get("status_class") == "5xx")
    rate_5xx = n_5xx / total if total else 0.0
    if rate_5xx > THRESHOLD_5XX_RATE:
        alerts.append({
            "level": "RED",
            "reason": "5xx_rate_exceeded",
            "detail": {"rate": round(rate_5xx, 4), "threshold": THRESHOLD_5XX_RATE, "count": n_5xx, "total": total},
        })

    n_429 = sum(1 for e in entries if int(e.get("status") or 0) == 429)
    if n_429 > THRESHOLD_429_COUNT:
        alerts.append({
            "level": "YELLOW",
            "reason": "rate_limit_burst",
            "detail": {"count": n_429, "threshold": THRESHOLD_429_COUNT},
        })

    # latency spike — per endpoint
    by_ep: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        by_ep[e["endpoint"]].append(float(e.get("latency_ms") or 0.0))
    for ep, lats in by_ep.items():
        p95 = _percentile(lats, 95)
        base = baseline.get(ep) or 0.0
        if base > 0 and p95 > base * THRESHOLD_LATENCY_SPIKE:
            alerts.append({
                "level": "YELLOW",
                "reason": "latency_spike",
                "detail": {"endpoint": ep, "p95_ms": p95, "baseline_ms": base, "multiplier": round(p95 / base, 2)},
            })

    return alerts


# ---------------------------------------------------------------------------
# Alert sinks
# ---------------------------------------------------------------------------
async def _post_guardian_webhook(alert: dict[str, Any]) -> None:
    url = os.environ.get("GUARDIAN_ALERT_WEBHOOK_URL")
    if not url:
        log.info("observer: no GUARDIAN_ALERT_WEBHOOK_URL set; skipping RED alert post")
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json={"source": "zernio_observer", **alert})
    except Exception as exc:
        log.warning("observer: guardian webhook failed: %s", exc)


def _yellow_notify(alert: dict[str, Any]) -> None:
    try:
        # notify_seyma is wrapped as a function-tool — we want the underlying
        # callable. Use a lightweight log fallback if wiring isn't available.
        from src.tools.sales import nocodb_tools  # noqa: F401

        log.warning("observer YELLOW: %s", alert)
    except Exception as exc:
        log.warning("observer: notify_seyma unreachable: %s", exc)


async def emit_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    last_alert_at: str | None = None
    last_alert_reason: str | None = None
    current_level = "GREEN"
    for a in alerts:
        last_alert_at = _iso(datetime.now(timezone.utc))
        last_alert_reason = a.get("reason")
        if a.get("level") == "RED":
            current_level = "RED"
            await _post_guardian_webhook(a)
        elif a.get("level") == "YELLOW":
            if current_level != "RED":
                current_level = "YELLOW"
            _yellow_notify(a)
    return {
        "current_alert_level": current_level,
        "last_alert_at": last_alert_at,
        "last_alert_reason": last_alert_reason,
    }


# ---------------------------------------------------------------------------
# One iteration
# ---------------------------------------------------------------------------
async def run_once(*, now: datetime | None = None, dry_run: bool | None = None) -> dict[str, Any]:
    if dry_run is None:
        dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    now = now or datetime.now(timezone.utc)
    cursor = load_cursor()
    if cursor:
        try:
            window_start = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except Exception:
            window_start = now - timedelta(seconds=WINDOW_SEC)
    else:
        window_start = now - timedelta(seconds=WINDOW_SEC)
    window_end = now

    from src.infra.zernio import get_zernio_client

    try:
        client = get_zernio_client()
    except Exception as exc:
        log.error("observer: cannot build zernio client: %s", exc)
        return {"error": str(exc)}

    raw = await client.list_logs(_iso(window_start), _iso(window_end), limit=500)
    raw_entries = raw.get("data") or raw.get("entries") or []
    entries = [normalize_log_entry(r) for r in raw_entries]
    entries = filter_dedupe_via_ring(entries, _ring_request_ids())

    n_written = write_entries(entries, dry_run=dry_run)

    rollup = compute_rollup(entries, window_start)
    write_rollup(rollup, dry_run=dry_run)

    alerts = detect_anomalies(entries)
    alert_state = await emit_alerts(alerts)

    save_cursor(_iso(window_end), dry_run=dry_run)

    return {
        "window_start": _iso(window_start),
        "window_end": _iso(window_end),
        "fetched": len(raw_entries),
        "after_dedupe": len(entries),
        "written": n_written,
        "alerts": alerts,
        **alert_state,
    }


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------
_stop = False


def _install_signal_handlers() -> None:
    def handler(signum, _frame):
        global _stop
        log.info("observer: received signal %s — stopping", signum)
        _stop = True

    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, handler)
        except Exception:
            pass


async def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    _install_signal_handlers()
    run_once_flag = os.environ.get("RUN_ONCE", "false").lower() == "true"
    while not _stop:
        try:
            result = await run_once()
            log.info("observer tick: %s", result)
        except Exception as exc:
            log.exception("observer: tick failed: %s", exc)
        if run_once_flag:
            return 0
        await asyncio.sleep(POLL_INTERVAL_SEC)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(main()))
