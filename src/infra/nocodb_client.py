"""NocoDB REST API client.

NocoDB v2 REST API kullanir:
    POST   /api/v2/tables/{tableId}/records  -> create
    GET    /api/v2/tables/{tableId}/records  -> list (with where filter)
    GET    /api/v2/tables/{tableId}/records/{Id} -> get one
    PATCH  /api/v2/tables/{tableId}/records  -> update (body: {Id: ..., fields...})
    DELETE /api/v2/tables/{tableId}/records  -> delete

Auth header: ``xc-token: {api_token}``

Usage:
    from src.infra.nocodb_client import get_nocodb_client

    client = get_nocodb_client()
    result = client.create_record(table_id, {"isim": "Ali", "telefon": "+90..."})
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from src.app.config import get_settings
from src.infra.errors import ServiceError, classify_error


_TIMEOUT_SECONDS = 30.0


class NocoDBClient:
    """Thin httpx wrapper around NocoDB v2 REST API.

    Hatalar `ServiceError` olarak yukselir; tool'lar `classify_error(exc, "nocodb")`
    ile structured dict'e cevirir.
    """

    def __init__(self, base_url: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "xc-token": api_token,
            "Content-Type": "application/json",
        }

    def _records_url(self, table_id: str) -> str:
        return f"{self._base_url}/api/v2/tables/{table_id}/records"

    def _request(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json,
                    params=params,
                )
        except httpx.TimeoutException as exc:
            raise ServiceError(
                f"NocoDB timeout: {exc}", service="nocodb"
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"NocoDB network error: {exc}", service="nocodb"
            ) from exc

        if response.status_code >= 400:
            raise ServiceError(
                f"NocoDB API Error {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                service="nocodb",
            )

        if not response.content:
            return {}
        return response.json()

    def create_record(self, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Insert one row. Returns the created record (with auto Id).

        NocoDB v2 records API expects body as an ARRAY of records (even for one row).
        Sending a single object yields 422 ERR_INVALID_PK_VALUE.
        """
        result = self._request("POST", self._records_url(table_id), json=[fields])
        if isinstance(result, list) and result:
            first = result[0]
            return first if isinstance(first, dict) else {"raw": first}
        return result if isinstance(result, dict) else {"raw": result}

    def update_record(
        self, table_id: str, record_id: int | str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing row. Body must include the primary key (Id).

        NocoDB v2 expects PATCH body as ARRAY of {Id, ...fields}.
        """
        body = [{"Id": record_id, **fields}]
        result = self._request("PATCH", self._records_url(table_id), json=body)
        if isinstance(result, list) and result:
            first = result[0]
            return first if isinstance(first, dict) else {"raw": first}
        return result if isinstance(result, dict) else {"raw": result}

    def get_record(self, table_id: str, record_id: int | str) -> dict[str, Any]:
        """Fetch a single record by primary key."""
        url = f"{self._records_url(table_id)}/{record_id}"
        return self._request("GET", url)

    def list_records(
        self,
        table_id: str,
        *,
        where: str | None = None,
        limit: int = 25,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """List rows with optional `where` filter (NocoDB syntax: '(field,eq,value)')."""
        params: dict[str, Any] = {"limit": limit}
        if where:
            params["where"] = where
        if sort:
            params["sort"] = sort
        return self._request("GET", self._records_url(table_id), params=params)

    def find_by_field(
        self, table_id: str, field: str, value: Any
    ) -> dict[str, Any] | None:
        """Lookup the first record matching field=value. Returns None if not found.

        Used as the first step of an idempotent upsert: check if a record with a
        unique key (e.g. external_id, leadgen_id) already exists.
        """
        where = f"({field},eq,{value})"
        result = self.list_records(table_id, where=where, limit=1)
        rows = result.get("list", []) if isinstance(result, dict) else []
        return rows[0] if rows else None

    def upsert_record(
        self, table_id: str, unique_field: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Idempotent upsert keyed by `unique_field`.

        Looks up the row by `fields[unique_field]`. If it exists, PATCHes the
        remaining fields onto it; otherwise POSTs a new row. Returns:
            {"created": bool, "record": dict}

        Raises ValueError if `unique_field` is not present in `fields`.
        Protects against duplicate INSERTs from webhook retries (P0 idempotency
        — see customer_agent/docs/NOCODB-SCHEMA-V2.md).
        """
        if unique_field not in fields or fields[unique_field] in (None, ""):
            raise ValueError(
                f"upsert_record: '{unique_field}' must be present in fields"
            )
        existing = self.find_by_field(table_id, unique_field, fields[unique_field])
        if existing is None:
            record = self.create_record(table_id, fields)
            return {"created": True, "record": record}
        record_id = existing.get("Id") or existing.get("id")
        record = self.update_record(table_id, record_id, fields)
        return {"created": False, "record": record}

    def delete_record(self, table_id: str, record_id: int | str) -> dict[str, Any]:
        """Delete one row by primary key."""
        body = {"Id": record_id}
        return self._request("DELETE", self._records_url(table_id), json=body)


@lru_cache(maxsize=1)
def get_nocodb_client() -> NocoDBClient:
    """Cached singleton NocoDB client built from env settings."""
    settings = get_settings()
    if not settings.nocodb_base_url or not settings.nocodb_api_token:
        raise ServiceError(
            "NocoDB not configured: NOCODB_BASE_URL and NOCODB_API_TOKEN are required.",
            service="nocodb",
            error_code_hint="AUTH_ERROR",
        )
    return NocoDBClient(
        base_url=settings.nocodb_base_url,
        api_token=settings.nocodb_api_token,
    )


__all__ = ["NocoDBClient", "get_nocodb_client", "classify_error"]
