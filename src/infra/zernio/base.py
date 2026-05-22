"""Shared HTTP plumbing for the Zernio API client.

Telemetry note (claude/zernio-logs-obs): every outbound call is funnelled
through ``_request`` which captures latency / status / payload size and
pushes to three sinks:
- Module-level ring buffer ``REQUEST_LOG`` (deque, max 1000)
- ``src.infra.zernio._metrics`` counters (calls_total + latency percentiles)
- Langfuse span (best-effort, soft-skip if env vars unset)

Telemetry failures NEVER break the original request — each sink is wrapped
in try/except and warnings are swallowed.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from typing import Any, Deque

import httpx

from src.infra.errors import ServiceError

log = logging.getLogger("zernio.base")

# Module-level ring buffer of recent requests. Operators read via
# /admin/zernio/recent-calls. ``maxlen=1000`` keeps RAM bounded.
REQUEST_LOG: Deque[dict[str, Any]] = deque(maxlen=1000)


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


def _payload_size(payload: Any) -> int:
    if payload is None:
        return 0
    try:
        if isinstance(payload, (bytes, bytearray)):
            return len(payload)
        if isinstance(payload, str):
            return len(payload.encode("utf-8"))
        import json as _json

        return len(_json.dumps(payload, default=str).encode("utf-8"))
    except Exception:
        return 0


async def _emit_langfuse_span(entry: dict[str, Any]) -> None:
    """Fire-and-forget Langfuse span. Soft-skip if env vars unset."""
    try:
        from src.app.config import get_settings

        s = get_settings()
        if not (
            getattr(s, "langfuse_public_key", None)
            and getattr(s, "langfuse_secret_key", None)
        ):
            return
        try:
            from langfuse import Langfuse  # type: ignore
        except Exception:
            return
        lf = Langfuse()
        lf.create_event(
            name="zernio.request",
            metadata={
                "endpoint": entry["endpoint"],
                "method": entry["method"],
                "status_class": entry["status_class"],
            },
        )
    except Exception as exc:  # pragma: no cover
        log.debug("langfuse emit failed: %s", exc)


class _ZernioBase:
    """Base HTTP client for Zernio v1 API."""

    TIMEOUT = 30  # seconds

    def __init__(
        self,
        api_key: str,
        account_id: str,
        base_url: str = "https://api.zernio.com/v1",
    ) -> None:
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = base_url.rstrip("/")

    def _headers(self, request_id: str | None = None) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if request_id:
            h["X-Request-ID"] = request_id
        return h

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise ServiceError(
                f"Zernio API error: {resp.text}",
                status_code=resp.status_code,
                service="zernio",
            )

    def _record_telemetry(self, entry: dict[str, Any]) -> None:
        try:
            REQUEST_LOG.append(entry)
        except Exception as exc:
            log.warning("zernio telemetry: ring-buffer push failed: %s", exc)

        try:
            from src.infra.zernio import _metrics

            _metrics.record(
                endpoint=entry["endpoint"],
                status_class=entry["status_class"],
                latency_ms=entry["latency_ms"],
            )
        except Exception as exc:
            log.warning("zernio telemetry: metrics record failed: %s", exc)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_emit_langfuse_span(entry))
        except Exception as exc:
            log.warning("zernio telemetry: langfuse task spawn failed: %s", exc)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        request_id = uuid.uuid4().hex
        if files is None:
            headers = self._headers(request_id=request_id)
        else:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Request-ID": request_id,
            }
        body_for_size = json if json is not None else data
        payload_size = _payload_size(body_for_size)

        t0 = time.monotonic()
        status = 0
        resp_size = 0
        error_code: str | None = None
        body_excerpt: str | None = None
        result: Any = None
        exc_to_raise: Exception | None = None

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                m = method.upper()
                url = self._url(path)
                if files is not None:
                    # multipart POST — only POST supported here
                    resp = await client.post(url, headers=headers, files=files, data=data or {})
                elif m == "GET":
                    resp = await client.get(url, headers=headers, params=params)
                elif m == "POST":
                    resp = await client.post(url, headers=headers, json=json)
                elif m == "PATCH":
                    resp = await client.patch(url, headers=headers, json=json)
                elif m == "PUT":
                    resp = await client.put(url, headers=headers, json=json)
                elif m == "DELETE":
                    resp = await client.request("DELETE", url, headers=headers, json=json)
                else:
                    resp = await client.request(m, url, headers=headers, params=params, json=json)
                status = resp.status_code
                try:
                    resp_size = len(resp.content or b"")
                except Exception:
                    resp_size = 0
                if status >= 400:
                    error_code = f"HTTP_{status}"
                    body_excerpt = (resp.text or "")[:500]
                    exc_to_raise = ServiceError(
                        f"Zernio API error: {resp.text}",
                        status_code=status,
                        service="zernio",
                    )
                else:
                    try:
                        result = resp.json()
                    except Exception:
                        result = resp.text
        except ServiceError:
            raise
        except Exception as exc:
            error_code = "NETWORK_ERROR"
            body_excerpt = str(exc)[:500]
            exc_to_raise = exc

        latency_ms = (time.monotonic() - t0) * 1000.0
        entry = {
            "request_id": request_id,
            "method": method.upper(),
            "endpoint": path,
            "payload_size": payload_size,
            "status": status,
            "status_class": _status_class(status) if status else "err",
            "latency_ms": round(latency_ms, 2),
            "response_size": resp_size,
            "timestamp": time.time(),
            "error_code": error_code,
            "body_excerpt": body_excerpt,
        }
        self._record_telemetry(entry)

        if exc_to_raise is not None:
            raise exc_to_raise
        return result

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict[str, Any]) -> Any:
        return await self._request("POST", path, json=json)

    async def _patch(self, path: str, json: dict[str, Any]) -> Any:
        return await self._request("PATCH", path, json=json)

    async def _put(self, path: str, json: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.put(self._url(path), headers=self._headers(), json=json)
            self._raise_for_status(resp)
            return resp.json()

    async def _delete(self, path: str, json: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.request(
                "DELETE", self._url(path), headers=self._headers(), json=json
            )
            self._raise_for_status(resp)
            return resp.json()

    async def _post_multipart(
        self,
        path: str,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", path, files=files, data=data)
