"""Sales REST API — deterministik raporlar, LLM'siz, ucuz.

Portal (mind-id) Sales dashboard'i bu endpoint'leri direkt cagirir.
Sales Manager (LLM) hala dogal dil sorulari icin var; portal artik
ona ihtiyac duymadan grafik/rakam uretir.

Auth: Bearer token (SALES_API_TOKEN env). Yoksa endpoint disabled.
Mind-id proxy route'u ayni token'i header'a koyar.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.tools.sales.reporting_tools import (
    _count_leads_impl,
    _lead_funnel_impl,
    _outreach_status_impl,
    _outreach_health_impl,
)

router = APIRouter(prefix="/sales", tags=["sales"])
_bearer = HTTPBearer(auto_error=False)


def _require_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Bearer auth. SALES_API_TOKEN env yoksa endpoint'ler 503 doner."""
    expected = os.environ.get("SALES_API_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SALES_API_TOKEN env yok — endpoint disabled.",
        )
    if creds is None or creds.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
        )


@router.get("/leads/count", dependencies=[Depends(_require_token)])
async def leads_count(
    asama: str | None = Query(None, description="Lead asamasi (Yeni|Sicak|...)"),
    kaynak: str | None = Query(None, description="Kanal (Meta Ads|Clay|...)"),
    atanan_kisi: str | None = Query(None, description="Atanan kisi"),
    date_from: str | None = Query(None, description="ISO YYYY-MM-DD"),
    date_to: str | None = Query(None, description="ISO YYYY-MM-DD"),
) -> dict[str, Any]:
    """Lead sayisi (opsiyonel filtre). Portal sicak lead kartinda kullanilir."""
    result = await _count_leads_impl(
        asama=asama,
        kaynak=kaynak,
        atanan_kisi=atanan_kisi,
        date_from=date_from,
        date_to=date_to,
    )
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "NocoDB read failed"))
    return result


@router.get("/leads/funnel", dependencies=[Depends(_require_token)])
async def leads_funnel(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> dict[str, Any]:
    """Funnel: her asamada kac lead. Portal donut/bar chart icin."""
    result = await _lead_funnel_impl(date_from=date_from, date_to=date_to)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "NocoDB read failed"))
    return result


@router.get("/outreach/status", dependencies=[Depends(_require_token)])
async def outreach_status() -> dict[str, Any]:
    """Outreach Robotu bugunku tempo: gonderilen, son saat, kalan kapasite."""
    result = await _outreach_status_impl()
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "NocoDB read failed"))
    return result


@router.get("/outreach/health", dependencies=[Depends(_require_token)])
async def outreach_health() -> dict[str, Any]:
    """Outreach pause durumu (Bekci karari). Portal kirmizi/yesil badge icin."""
    result = await _outreach_health_impl()
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Guardian read failed"))
    return result
