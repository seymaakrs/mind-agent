"""
NocoDB CRM REST API v2 client.

customer_agent ekosisteminin veri katmaniyla (NocoDB) konusmak icin kullanilir.
Sozlesme: docs/customer-integration-contract.md

Kapsam (Bolum 2):
- Tablo whitelist: leads, pipeline, etkilesimler. Diger tablolar TANINMAZ.
- Yazma whitelist (sadece leads): notlar, seo_raporu_url, son_analiz_tarihi.
  Bunun disinda bir kolona PATCH atmak ValueError firlatir (programlama hatasi).
- Hata davranisi: structured ServiceError dict (mind-agent geneli pattern,
  src/infra/errors.py ile uyumlu).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel


# Sozlesmedeki yazma whitelist'i (Bolum 2). Bu liste DISINDA hicbir kolon
# update_lead ile dokunulamaz; mind-agent satis verisine yazma yetkisi almaz.
NOCODB_WRITABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "notlar",
        "seo_raporu_url",
        "son_analiz_tarihi",
    }
)


@dataclass(frozen=True)
class NocoDBConfig:
    """NocoDB baglanti konfigurasyonu — Settings'den olusturulur."""

    base_url: str
    api_token: str
    base_id: str
    table_leads: str
    table_pipeline: str
    table_etkilesimler: str

    @classmethod
    def from_settings(
        cls,
        base_url: str | None,
        api_token: str | None,
        base_id: str | None,
        table_leads: str | None,
        table_pipeline: str | None,
        table_etkilesimler: str | None,
    ) -> "NocoDBConfig":
        """
        Settings'den NocoDBConfig olusturur. Eksik field varsa ValueError.

        Bu sayede customer_agent capability'leri acilirken erken (startup'ta)
        konfig eksigi yakalanir, runtime'da degil.
        """
        missing = [
            name for name, value in [
                ("NOCODB_BASE_URL", base_url),
                ("NOCODB_API_TOKEN", api_token),
                ("NOCODB_BASE_ID", base_id),
                ("NOCODB_TABLE_LEADS", table_leads),
                ("NOCODB_TABLE_PIPELINE", table_pipeline),
                ("NOCODB_TABLE_ETKILESIMLER", table_etkilesimler),
            ]
            if not value
        ]
        if missing:
            raise ValueError(
                f"NocoDBConfig eksik env: {', '.join(missing)}"
            )
        return cls(
            base_url=base_url.rstrip("/"),
            api_token=api_token,
            base_id=base_id,
            table_leads=table_leads,
            table_pipeline=table_pipeline,
            table_etkilesimler=table_etkilesimler,
        )


def _service_error(
    error_code: str,
    error: str,
    retryable: bool,
    user_message_tr: str,
    retry_after_seconds: int | None = None,
) -> dict[str, Any]:
    """ServiceError pattern (src/infra/errors.py ile uyumlu) dict uretir."""
    out: dict[str, Any] = {
        "success": False,
        "service": "nocodb",
        "error": error,
        "error_code": error_code,
        "retryable": retryable,
        "user_message_tr": user_message_tr,
    }
    if retry_after_seconds is not None:
        out["retry_after_seconds"] = retry_after_seconds
    return out


def _classify_http_status(status: int, body: str) -> dict[str, Any]:
    """HTTP status code'u mind-agent ServiceError pattern'ine map'ler."""
    if status == 401 or status == 403:
        return _service_error(
            error_code="AUTH_ERROR",
            error=f"NocoDB auth failed (status {status}): {body[:200]}",
            retryable=False,
            user_message_tr="CRM kimlik dogrulama hatasi. API token kontrol edilmeli.",
        )
    if status == 404:
        return _service_error(
            error_code="NOT_FOUND",
            error=f"NocoDB record not found: {body[:200]}",
            retryable=False,
            user_message_tr="Aranilan kayit CRM'de bulunamadi.",
        )
    if status == 429:
        return _service_error(
            error_code="RATE_LIMIT",
            error="NocoDB rate limit",
            retryable=True,
            user_message_tr="CRM su an yogun. Birazdan tekrar denenecek.",
            retry_after_seconds=30,
        )
    if 500 <= status < 600:
        return _service_error(
            error_code="SERVER_ERROR",
            error=f"NocoDB server error {status}: {body[:200]}",
            retryable=True,
            user_message_tr="CRM gecici bir hata verdi.",
            retry_after_seconds=10,
        )
    return _service_error(
        error_code="UNKNOWN",
        error=f"NocoDB unexpected status {status}: {body[:200]}",
        retryable=False,
        user_message_tr="CRM beklenmeyen bir cevap dondu.",
    )


class NocoDBClient:
    """NocoDB REST API v2 ile konusan async client.

    Whitelist enforcement: sadece sozlesmede tanimli tablolar/kolonlar
    erisilebilir. Yazma kolonlari NOCODB_WRITABLE_COLUMNS ile sinirli.
    """

    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(self, config: NocoDBConfig, timeout: float | None = None):
        self.config = config
        self.timeout = timeout or self.DEFAULT_TIMEOUT_SECONDS

    def _headers(self) -> dict[str, str]:
        return {
            "xc-token": self.config.api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _records_url(self, table_id: str) -> str:
        return f"{self.config.base_url}/api/v2/tables/{table_id}/records"

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ortak GET — hatalari ServiceError'a cevirir."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                response = await http.get(url, headers=self._headers(), params=params)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as exc:
            return _service_error(
                error_code="NETWORK_ERROR",
                error=f"NocoDB unreachable: {exc}",
                retryable=True,
                user_message_tr="CRM'e su an erisilemiyor.",
                retry_after_seconds=15,
            )

        if response.status_code != 200:
            return _classify_http_status(response.status_code, response.text)

        return {"success": True, "data": response.json()}

    async def _patch(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """Ortak PATCH — hatalari ServiceError'a cevirir."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                response = await http.patch(url, headers=self._headers(), json=body)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as exc:
            return _service_error(
                error_code="NETWORK_ERROR",
                error=f"NocoDB unreachable: {exc}",
                retryable=True,
                user_message_tr="CRM'e su an erisilemiyor.",
                retry_after_seconds=15,
            )

        if response.status_code not in (200, 201):
            return _classify_http_status(response.status_code, response.text)

        return {"success": True, "data": response.json()}

    # -------------------------------------------------------------------
    # Public API — Leads
    # -------------------------------------------------------------------

    async def list_leads(
        self,
        where: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Leadler tablosundan kayit listesi oku."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if where:
            params["where"] = where

        result = await self._get(self._records_url(self.config.table_leads), params=params)
        if not result["success"]:
            return result

        data = result["data"]
        return {
            "success": True,
            "records": data.get("list", []),
            "page_info": data.get("pageInfo", {}),
        }

    async def get_lead(self, lead_id: int | str) -> dict[str, Any]:
        """Tek lead'i ID ile oku."""
        url = f"{self._records_url(self.config.table_leads)}/{lead_id}"
        result = await self._get(url)
        if not result["success"]:
            return result
        return {"success": True, "record": result["data"]}

    async def update_lead(
        self,
        lead_id: int | str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Lead'in BELIRLI kolonlarini guncelle. Sadece NOCODB_WRITABLE_COLUMNS
        listesindekiler kabul edilir; disindaki bir kolon → ValueError.

        Bu, IDOR/yetki disi yazma'yi sozlesme katmaninda engeller (defense in depth).
        """
        if not fields:
            raise ValueError("update_lead: fields bos olamaz")

        non_writable = [c for c in fields.keys() if c not in NOCODB_WRITABLE_COLUMNS]
        if non_writable:
            raise ValueError(
                f"NocoDB columns not writable by mind-agent: {non_writable}. "
                f"Allowed: {sorted(NOCODB_WRITABLE_COLUMNS)}"
            )

        # NocoDB v2 PATCH: body'de Id zorunlu (Id kolonu uppercase).
        body = {"Id": lead_id, **fields}
        url = self._records_url(self.config.table_leads)
        result = await self._patch(url, body)
        if not result["success"]:
            return result
        return {"success": True, "record": result["data"]}

    # -------------------------------------------------------------------
    # Public API — Pipeline
    # -------------------------------------------------------------------

    async def list_pipeline(
        self,
        where: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Pipeline tablosundan kayit listesi oku."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if where:
            params["where"] = where

        result = await self._get(self._records_url(self.config.table_pipeline), params=params)
        if not result["success"]:
            return result
        data = result["data"]
        return {
            "success": True,
            "records": data.get("list", []),
            "page_info": data.get("pageInfo", {}),
        }

    # -------------------------------------------------------------------
    # Public API — Etkilesimler
    # -------------------------------------------------------------------

    async def list_etkilesimler(
        self,
        lead_id: int | str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Etkilesimler tablosu — opsiyonel lead bazli filtre."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if lead_id is not None:
            # NocoDB v2 'where' syntax: (kolon,operator,deger)
            params["where"] = f"(lead,eq,{lead_id})"

        result = await self._get(
            self._records_url(self.config.table_etkilesimler), params=params
        )
        if not result["success"]:
            return result
        data = result["data"]
        return {
            "success": True,
            "records": data.get("list", []),
            "page_info": data.get("pageInfo", {}),
        }


__all__ = [
    "NocoDBClient",
    "NocoDBConfig",
    "NOCODB_WRITABLE_COLUMNS",
]
