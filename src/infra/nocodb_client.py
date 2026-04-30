"""NocoDB v2 REST API client for Customer Agent (Sales) system.

Design notes
------------
- Async-first: uses httpx.AsyncClient. Tools call this in async context.
- Tolerant reader: missing optional fields default to None / [] / {}.
- Schema source of truth: ``customer_agent/docs/NOCODB-SCHEMA-V2.md``.
- Error handling: HTTP errors -> ServiceError with status_code and service="nocodb".
  Tools wrap calls in try/except and call ``classify_error(exc, "nocodb")`` to get
  a structured dict for the agent.

NocoDB v2 endpoints used
------------------------
- Records:    GET/POST/PATCH/DELETE /api/v2/tables/{table_id}/records
- Get one:    GET /api/v2/tables/{table_id}/records/{record_id}
- POST/PATCH bodies are arrays of objects (NocoDB convention).

Authentication: ``xc-token`` header.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.infra.errors import ServiceError


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class NocoDBConfig:
    """Configuration for NocoDB client.

    Required:
        base_url: NocoDB instance URL (e.g. "https://nocodb.example.com")
        api_token: NocoDB API token (xc-token)
        leads_table_id: Table ID for `leads`
        messages_table_id: Table ID for `lead_messages`
        notifications_table_id: Table ID for `seyma_notifications`

    Optional (V2 schema additions; clients that don't need them can omit):
        campaigns_table_id, daily_metrics_table_id, decisions_log_table_id,
        objections_log_table_id, agent_health_table_id
    """

    base_url: str
    api_token: str
    leads_table_id: str
    messages_table_id: str
    notifications_table_id: str
    campaigns_table_id: str | None = None
    daily_metrics_table_id: str | None = None
    decisions_log_table_id: str | None = None
    objections_log_table_id: str | None = None
    agent_health_table_id: str | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        # Strip trailing slash to keep URL building consistent.
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")
        if not self.base_url:
            raise ValueError("NocoDBConfig.base_url is required")
        if not self.api_token:
            raise ValueError("NocoDBConfig.api_token is required")
        if not self.leads_table_id:
            raise ValueError("NocoDBConfig.leads_table_id is required")
        if not self.messages_table_id:
            raise ValueError("NocoDBConfig.messages_table_id is required")
        if not self.notifications_table_id:
            raise ValueError("NocoDBConfig.notifications_table_id is required")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class NocoDBClient:
    """Thin async wrapper around NocoDB v2 REST API.

    Usage::

        client = NocoDBClient(NocoDBConfig(...))
        record = await client.create_record("t_leads", {"name": "Ali", "phone": "+90..."})
        rows = await client.query_records("t_leads", where="(lead_score,gte,8)", limit=50)
    """

    def __init__(self, config: NocoDBConfig) -> None:
        self.config = config
        self._async_client = httpx.AsyncClient(timeout=config.timeout_seconds)

    # ------------------------------------------------------------------ helpers

    def _headers(self) -> dict[str, str]:
        return {
            "xc-token": self.config.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _records_url(self, table_id: str, record_id: int | str | None = None) -> str:
        if not table_id:
            raise ValueError("table_id must not be empty")
        base = f"{self.config.base_url}/api/v2/tables/{table_id}/records"
        if record_id is not None:
            return f"{base}/{record_id}"
        return base

    def _raise_service_error(
        self, exc: httpx.HTTPStatusError, action: str
    ) -> None:
        status = exc.response.status_code if exc.response is not None else None
        message = f"NocoDB {action} failed (HTTP {status}): {exc.response.text if exc.response else exc}"
        raise ServiceError(message, status_code=status, service="nocodb") from exc

    # ------------------------------------------------------------------ CRUD

    async def create_record(
        self, table_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a single record. Returns the created row payload (incl. Id).

        NocoDB v2 expects an array body; we wrap and unwrap transparently.
        """
        url = self._records_url(table_id)
        try:
            resp = await self._async_client.post(
                url, headers=self._headers(), json=[fields]
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "create_record")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB create_record network error: {exc}",
                status_code=None,
                service="nocodb",
            ) from exc

        data = resp.json()
        # NocoDB sometimes returns a list, sometimes a single dict. Normalize.
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        return {"raw": data}

    async def update_record(
        self, table_id: str, record_id: int | str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing record by Id. Returns updated payload."""
        url = self._records_url(table_id)
        body = [{"Id": record_id, **fields}]
        try:
            resp = await self._async_client.patch(
                url, headers=self._headers(), json=body
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "update_record")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB update_record network error: {exc}",
                status_code=None,
                service="nocodb",
            ) from exc

        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        return {"raw": data}

    async def get_record(
        self, table_id: str, record_id: int | str
    ) -> dict[str, Any]:
        """Read a single record by Id."""
        url = self._records_url(table_id, record_id)
        try:
            resp = await self._async_client.get(url, headers=self._headers())
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "get_record")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB get_record network error: {exc}",
                status_code=None,
                service="nocodb",
            ) from exc
        return resp.json()

    async def query_records(
        self,
        table_id: str,
        *,
        where: str | None = None,
        sort: str | None = None,
        fields: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query records. Tolerant: returns [] if response missing 'list'.

        Args:
            where: NocoDB filter expression e.g. ``(lead_score,gte,8)``.
            sort: ``-CreatedAt`` for desc, ``CreatedAt`` for asc.
            fields: comma-separated fields to return.
            limit: max rows (NocoDB caps at 1000).
            offset: pagination offset.
        """
        url = self._records_url(table_id)
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if where:
            params["where"] = where
        if sort:
            params["sort"] = sort
        if fields:
            params["fields"] = fields

        try:
            resp = await self._async_client.get(
                url, headers=self._headers(), params=params
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "query_records")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB query_records network error: {exc}",
                status_code=None,
                service="nocodb",
            ) from exc

        data = resp.json()
        if isinstance(data, dict):
            return list(data.get("list", []))
        return []

    async def delete_record(
        self, table_id: str, record_id: int | str
    ) -> bool:
        """Delete a record. Returns True on success."""
        url = self._records_url(table_id)
        body = [{"Id": record_id}]
        try:
            resp = await self._async_client.request(
                "DELETE", url, headers=self._headers(), json=body
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "delete_record")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB delete_record network error: {exc}",
                status_code=None,
                service="nocodb",
            ) from exc
        return True

    async def aclose(self) -> None:
        """Close underlying httpx client. Call on shutdown."""
        await self._async_client.aclose()


__all__ = ["NocoDBClient", "NocoDBConfig"]
