"""Tests for the Zernio observability surface (claude/zernio-logs-obs).

Covers:
- Client-side telemetry: ring buffer, counters, Langfuse soft-skip, error capture
- Anomaly thresholds: 5xx rate, 429 burst, latency spike
- Idempotent Firestore ingestion
- Cursor resume
- Dedupe via X-Request-ID
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _client():
    from src.infra.zernio import ZernioClient

    return ZernioClient(api_key="sk_test", account_id="acc", base_url="https://api.zernio.com/v1")


def _mock_response(status: int, json_body: Any = None, text_body: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text_body or (str(json_body) if json_body else "")
    resp.content = (text_body or str(json_body or "")).encode()
    resp.json = MagicMock(return_value=json_body if json_body is not None else {})
    return resp


@pytest.fixture(autouse=True)
def _reset_state():
    from src.infra.zernio import _metrics
    from src.infra.zernio.base import REQUEST_LOG

    REQUEST_LOG.clear()
    _metrics.reset()
    yield
    REQUEST_LOG.clear()
    _metrics.reset()


# ---------------------------------------------------------------------------
# Client-side telemetry
# ---------------------------------------------------------------------------
class TestRingBuffer:
    @pytest.mark.asyncio
    async def test_successful_request_recorded(self):
        from src.infra.zernio.base import REQUEST_LOG

        c = _client()
        with patch.object(httpx.AsyncClient, "get",
                          new=AsyncMock(return_value=_mock_response(200, {"ok": True}))):
            await c._get("/whatsapp/contacts", params={"limit": 10})
        assert len(REQUEST_LOG) == 1
        entry = REQUEST_LOG[0]
        assert entry["status"] == 200
        assert entry["status_class"] == "2xx"
        assert entry["endpoint"] == "/whatsapp/contacts"
        assert entry["method"] == "GET"
        assert entry["request_id"]
        assert entry["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_error_request_recorded_with_excerpt(self):
        from src.infra.errors import ServiceError
        from src.infra.zernio.base import REQUEST_LOG

        c = _client()
        with patch.object(httpx.AsyncClient, "post",
                          new=AsyncMock(return_value=_mock_response(500, text_body="boom" * 200))):
            with pytest.raises(ServiceError):
                await c._post("/whatsapp/bulk", json={"x": 1})
        assert len(REQUEST_LOG) == 1
        entry = REQUEST_LOG[0]
        assert entry["status"] == 500
        assert entry["status_class"] == "5xx"
        assert entry["error_code"] == "HTTP_500"
        assert entry["body_excerpt"] and len(entry["body_excerpt"]) <= 500

    @pytest.mark.asyncio
    async def test_ring_buffer_caps_at_1000(self):
        from src.infra.zernio.base import REQUEST_LOG

        c = _client()
        with patch.object(httpx.AsyncClient, "request",
                          new=AsyncMock(return_value=_mock_response(200, {}))):
            for _ in range(1100):
                await c._get("/x")
        assert len(REQUEST_LOG) == 1000

    @pytest.mark.asyncio
    async def test_x_request_id_header_sent(self):
        c = _client()
        captured = {}

        async def fake_request(method, url, **kw):
            captured["headers"] = kw.get("headers")
            return _mock_response(200, {})

        with patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=fake_request)):
            await c._get("/x")
        assert "X-Request-ID" in captured["headers"]
        assert len(captured["headers"]["X-Request-ID"]) == 32  # uuid4 hex


class TestLangfuseSoftSkip:
    @pytest.mark.asyncio
    async def test_no_langfuse_keys_no_crash(self):
        """When Langfuse env unset, telemetry still works fine."""
        c = _client()
        with patch.dict(os.environ, {}, clear=False):
            for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
                os.environ.pop(k, None)
            with patch.object(httpx.AsyncClient, "request",
                              new=AsyncMock(return_value=_mock_response(200, {}))):
                await c._get("/x")  # must not raise


class TestMetricsCounters:
    @pytest.mark.asyncio
    async def test_calls_total_increments(self):
        from src.infra.zernio import _metrics

        c = _client()
        with patch.object(httpx.AsyncClient, "request",
                          new=AsyncMock(return_value=_mock_response(200, {}))):
            await c._get("/a")
            await c._get("/a")
            await c._get("/b")
        assert _metrics.calls_total[("/a", "2xx")] == 2
        assert _metrics.calls_total[("/b", "2xx")] == 1

    @pytest.mark.asyncio
    async def test_latency_percentiles(self):
        from src.infra.zernio import _metrics

        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            _metrics.record("/x", "2xx", v)
        assert _metrics.latency_p50("/x") > 0
        assert _metrics.latency_p95("/x") >= _metrics.latency_p50("/x")


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------
def _entry(status=200, endpoint="/x", latency_ms=100.0, rid="r1"):
    from src.agents.zernio_observer.runner import _status_class

    return {
        "log_id": rid,
        "request_id": rid,
        "timestamp": "2026-05-22T00:00:00Z",
        "level": "info",
        "endpoint": endpoint,
        "method": "GET",
        "status": status,
        "latency_ms": latency_ms,
        "status_class": _status_class(status),
        "raw": {},
    }


class TestAnomalyThresholds:
    def test_5xx_rate_triggers_red(self):
        from src.agents.zernio_observer.runner import detect_anomalies

        entries = [_entry(status=500, rid=f"r{i}") for i in range(10)] + \
                  [_entry(status=200, rid=f"s{i}") for i in range(90)]
        alerts = detect_anomalies(entries)
        red = [a for a in alerts if a["level"] == "RED"]
        assert red and red[0]["reason"] == "5xx_rate_exceeded"

    def test_5xx_rate_below_threshold_no_alert(self):
        from src.agents.zernio_observer.runner import detect_anomalies

        entries = [_entry(status=500, rid=f"r{i}") for i in range(2)] + \
                  [_entry(status=200, rid=f"s{i}") for i in range(98)]
        alerts = detect_anomalies(entries)
        assert not any(a["reason"] == "5xx_rate_exceeded" for a in alerts)

    def test_429_burst_triggers_yellow(self):
        from src.agents.zernio_observer.runner import detect_anomalies

        entries = [_entry(status=429, rid=f"r{i}") for i in range(60)]
        alerts = detect_anomalies(entries)
        assert any(a["level"] == "YELLOW" and a["reason"] == "rate_limit_burst" for a in alerts)

    def test_latency_spike_triggers_yellow(self):
        from src.agents.zernio_observer.runner import detect_anomalies

        entries = [_entry(latency_ms=2000.0, rid=f"r{i}") for i in range(20)]
        alerts = detect_anomalies(entries, baseline_p95_by_endpoint={"/x": 100.0})
        assert any(a["reason"] == "latency_spike" for a in alerts)

    def test_no_baseline_no_latency_alert(self):
        from src.agents.zernio_observer.runner import detect_anomalies

        entries = [_entry(latency_ms=9999.0, rid=f"r{i}") for i in range(10)]
        alerts = detect_anomalies(entries, baseline_p95_by_endpoint={})
        assert not any(a["reason"] == "latency_spike" for a in alerts)


# ---------------------------------------------------------------------------
# Ingestion (idempotent + dedupe + cursor)
# ---------------------------------------------------------------------------
class TestIngestion:
    def test_write_entries_idempotent_via_logId(self):
        from src.agents.zernio_observer.runner import write_entries

        fake_doc = MagicMock()
        fake_db = MagicMock()
        fake_db.collection.return_value.document.return_value.collection.return_value.document.return_value = fake_doc

        with patch("src.agents.zernio_observer.runner._firestore", return_value=fake_db):
            entries = [_entry(rid="log-1"), _entry(rid="log-1"), _entry(rid="log-2")]
            n = write_entries(entries)
        assert n == 3
        # Each .set() call uses merge=True -> idempotent on collision
        for call in fake_doc.set.call_args_list:
            assert call.kwargs.get("merge") is True

    def test_dry_run_no_writes(self):
        from src.agents.zernio_observer.runner import write_entries

        with patch("src.agents.zernio_observer.runner._firestore") as fs:
            n = write_entries([_entry()], dry_run=True)
        assert n == 1
        fs.assert_not_called()

    def test_dedupe_via_ring_buffer(self):
        from src.agents.zernio_observer.runner import filter_dedupe_via_ring

        entries = [_entry(rid="a"), _entry(rid="b"), _entry(rid="c")]
        out = filter_dedupe_via_ring(entries, {"a", "c"})
        rids = [e["request_id"] for e in out]
        assert rids == ["b"]

    def test_dedupe_passthrough_when_no_rid(self):
        from src.agents.zernio_observer.runner import filter_dedupe_via_ring

        entries = [{**_entry(rid=""), "request_id": ""}]
        out = filter_dedupe_via_ring(entries, {"a"})
        assert len(out) == 1


class TestCursor:
    def test_save_and_load_cursor(self):
        from src.agents.zernio_observer.runner import load_cursor, save_cursor

        fake_db = MagicMock()
        fake_doc = MagicMock()
        fake_doc.exists = True
        fake_doc.to_dict.return_value = {"cursor": "2026-05-22T00:05:00Z"}
        fake_db.collection.return_value.document.return_value.get.return_value = fake_doc

        with patch("src.agents.zernio_observer.runner._firestore", return_value=fake_db):
            assert load_cursor() == "2026-05-22T00:05:00Z"
            save_cursor("2026-05-22T00:10:00Z")
        # set was called with merge=True
        set_calls = fake_db.collection.return_value.document.return_value.set.call_args_list
        assert set_calls and set_calls[0].kwargs.get("merge") is True

    def test_load_cursor_missing_returns_none(self):
        from src.agents.zernio_observer.runner import load_cursor

        fake_db = MagicMock()
        fake_doc = MagicMock()
        fake_doc.exists = False
        fake_db.collection.return_value.document.return_value.get.return_value = fake_doc
        with patch("src.agents.zernio_observer.runner._firestore", return_value=fake_db):
            assert load_cursor() is None


# ---------------------------------------------------------------------------
# Rollup shape
# ---------------------------------------------------------------------------
class TestRollup:
    def test_rollup_counts_and_percentiles(self):
        from src.agents.zernio_observer.runner import compute_rollup

        entries = [
            _entry(status=200, endpoint="/a", latency_ms=10),
            _entry(status=200, endpoint="/a", latency_ms=20),
            _entry(status=500, endpoint="/b", latency_ms=200),
        ]
        ws = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
        r = compute_rollup(entries, ws)
        assert r["day"] == "2026-05-22"
        assert r["hhmm"] == "1200"
        assert r["total_calls"] == 3
        assert r["counts"]["/a|2xx"] == 2
        assert r["counts"]["/b|5xx"] == 1
        assert r["endpoints"]["/a"]["count"] == 2


# ---------------------------------------------------------------------------
# Logs API mixin
# ---------------------------------------------------------------------------
class TestLogsMixin:
    @pytest.mark.asyncio
    async def test_list_logs_builds_correct_params(self):
        c = _client()
        captured = {}

        async def fake_request(method, url, **kw):
            captured["url"] = url
            captured["params"] = kw.get("params")
            return _mock_response(200, {"data": []})

        with patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=fake_request)):
            await c.list_logs("2026-05-22T00:00:00Z", "2026-05-22T00:05:00Z", level="error", limit=50, page=2)
        assert captured["url"].endswith("/logs")
        assert captured["params"]["fromDate"] == "2026-05-22T00:00:00Z"
        assert captured["params"]["toDate"] == "2026-05-22T00:05:00Z"
        assert captured["params"]["level"] == "error"
        assert captured["params"]["limit"] == 50
        assert captured["params"]["page"] == 2
