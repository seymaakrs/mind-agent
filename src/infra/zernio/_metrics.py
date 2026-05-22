"""In-process metrics for Zernio outbound calls.

Light-weight Prometheus-like counters + latency reservoir, kept in module
state. Reset on process restart — Zernio Logs API poller is the durable
sink (Firestore). This module is the *operator status endpoint* sink.

Thread/asyncio-safe enough for our usage: counters are simple int adds,
latency reservoirs are bounded deques.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque

# {(endpoint, status_class): count}
calls_total: dict[tuple[str, str], int] = defaultdict(int)

# per-endpoint latency reservoir (last 1000 samples)
_LAT_RESERVOIR: dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=1000))

# All latencies (cross-endpoint) for the global p50/p95
_LAT_ALL: Deque[float] = deque(maxlen=5000)


def record(endpoint: str, status_class: str, latency_ms: float) -> None:
    calls_total[(endpoint, status_class)] += 1
    _LAT_RESERVOIR[endpoint].append(latency_ms)
    _LAT_ALL.append(latency_ms)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def latency_p50(endpoint: str | None = None) -> float:
    src = list(_LAT_RESERVOIR[endpoint]) if endpoint else list(_LAT_ALL)
    return _percentile(src, 50)


def latency_p95(endpoint: str | None = None) -> float:
    src = list(_LAT_RESERVOIR[endpoint]) if endpoint else list(_LAT_ALL)
    return _percentile(src, 95)


def snapshot() -> dict:
    """Operator-facing snapshot of all counters + global percentiles."""
    by_endpoint: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (endpoint, status_class), count in calls_total.items():
        by_endpoint[endpoint][status_class] = count
    return {
        "calls_total": {f"{e}|{c}": n for (e, c), n in calls_total.items()},
        "by_endpoint": {k: dict(v) for k, v in by_endpoint.items()},
        "latency_p50_ms": latency_p50(),
        "latency_p95_ms": latency_p95(),
        "endpoints": list(_LAT_RESERVOIR.keys()),
    }


def reset() -> None:
    """Test helper — clears all in-process state."""
    calls_total.clear()
    _LAT_RESERVOIR.clear()
    _LAT_ALL.clear()
