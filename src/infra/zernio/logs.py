"""Zernio Logs API client mixin.

API ASSUMPTION (documented — verify against Zernio docs before prod):
    GET /v1/logs
    Query params:
        fromDate   ISO-8601 (e.g. 2026-05-22T00:00:00Z)
        toDate     ISO-8601
        level      optional — info|warn|error
        limit      page size (default 100)
        page       1-indexed page number
    Response shape (assumed):
        {
            "data": [
                {
                    "id": str,                # log entry id
                    "requestId": str,         # MUST match X-Request-ID we sent
                    "timestamp": str,         # ISO-8601
                    "level": str,
                    "endpoint": str,
                    "method": str,
                    "status": int,
                    "latencyMs": float,
                    "message": str,
                    ...
                }
            ],
            "page": int,
            "limit": int,
            "total": int
        }

If Zernio's actual schema differs, only the keys above need remapping in
``src.agents.zernio_observer.runner.ingest_logs``.
"""
from __future__ import annotations

from typing import Any


class _LogsMixin:
    """Adds ``list_logs(...)`` to :class:`ZernioClient`."""

    async def list_logs(
        self,
        date_from: str,
        date_to: str,
        level: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Fetch Zernio platform logs for a time window.

        Args mirror Zernio's documented Logs API. ``date_from``/``date_to``
        must be ISO-8601 UTC strings.
        """
        params: dict[str, Any] = {
            "fromDate": date_from,
            "toDate": date_to,
            "limit": limit,
            "page": page,
        }
        if level:
            params["level"] = level
        return await self._get("/logs", params=params)
