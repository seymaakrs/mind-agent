"""Shared HTTP plumbing for the Zernio API client."""
from __future__ import annotations

from typing import Any

import httpx

from src.infra.errors import ServiceError


class _ZernioBase:
    """Base HTTP client for Zernio v1 API.

    Auth is Bearer (matches Late). Status >= 400 is converted to a
    ``ServiceError`` so tool wrappers can ``classify_error(exc, "zernio")``.
    """

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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(self._url(path), headers=self._headers(), params=params)
            self._raise_for_status(resp)
            return resp.json()

    async def _post(self, path: str, json: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.post(self._url(path), headers=self._headers(), json=json)
            self._raise_for_status(resp)
            return resp.json()

    async def _patch(self, path: str, json: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.patch(self._url(path), headers=self._headers(), json=json)
            self._raise_for_status(resp)
            return resp.json()
