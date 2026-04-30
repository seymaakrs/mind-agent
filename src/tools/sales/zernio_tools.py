"""Zernio social media tools — exposed to IG DM, LinkedIn, Meta sales agents.

These wrap ``ZernioClient`` with ``@function_tool`` decorators and add the
sales-specific bookkeeping (CBO compliance check before sending).
"""
from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.errors import classify_error
from src.infra.zernio_client import (
    ZernioFeatureNotEnabledError,
    ZernioPlatform,
    get_zernio_client,
)
from src.tools.sales.clay_tools import _is_cbo_compliant


_PLATFORM_MAP: dict[str, ZernioPlatform] = {
    "instagram": ZernioPlatform.INSTAGRAM,
    "facebook": ZernioPlatform.FACEBOOK,
    "linkedin": ZernioPlatform.LINKEDIN,
    "whatsapp": ZernioPlatform.WHATSAPP,
    "meta": ZernioPlatform.META,
    "tiktok": ZernioPlatform.TIKTOK,
    "x": ZernioPlatform.X,
    "threads": ZernioPlatform.THREADS,
}


def _resolve_platform(value: str) -> ZernioPlatform | None:
    return _PLATFORM_MAP.get(value.strip().lower())


# ---------------------------------------------------------------------------
# Send DM
# ---------------------------------------------------------------------------


@function_tool
async def send_zernio_dm(
    platform: str,
    account_id: str,
    recipient_id: str,
    text: str,
    thread_id: str | None = None,
    enforce_cbo: bool = True,
) -> dict[str, Any]:
    """Bir sosyal platform üzerinden DM gönderir (Zernio Inbox üzerinden).

    Args:
        platform: ``instagram`` | ``facebook`` | ``linkedin`` | ``whatsapp`` | ``meta``.
        account_id: Zernio'ya bağlı sosyal hesap ID'si.
        recipient_id: Mesajın gideceği kullanıcı ID'si.
        text: Mesaj metni (Türkçe).
        thread_id: Var olan konuşmaya yanıt veriyorsan thread ID.
        enforce_cbo: True ise yasakli ifade içeren mesajlar gönderilmez.

    Returns:
        ``{"success": True, "message_id": str, ...}`` veya yapılandırılmış hata.
    """
    plat = _resolve_platform(platform)
    if plat is None:
        return {
            "success": False,
            "error": f"Unknown Zernio platform '{platform}'",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }

    if enforce_cbo:
        compliant, hits = _is_cbo_compliant(text)
        if not compliant:
            return {
                "success": False,
                "error": (
                    f"Message contains forbidden phrases (CBO violation): {hits}. "
                    "Rewrite without urgency/pressure language."
                ),
                "error_code": "CONTENT_POLICY",
                "retryable": False,
                "violations": hits,
            }

    try:
        client = get_zernio_client()
        result = await client.send_dm(
            platform=plat,
            account_id=account_id,
            recipient_id=recipient_id,
            text=text,
            thread_id=thread_id,
        )
        return {"success": True, **result}
    except ZernioFeatureNotEnabledError as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "INSUFFICIENT_BALANCE",  # addon disabled
            "retryable": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "zernio")}


# ---------------------------------------------------------------------------
# List DM threads
# ---------------------------------------------------------------------------


@function_tool
async def list_zernio_dm_threads(
    platform: str,
    account_id: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Bir hesabın son DM threadlerini listeler.

    Args:
        platform: ``instagram`` | ``facebook`` | ``linkedin`` | ``whatsapp`` | ``meta``.
        account_id: Zernio'ya bağlı sosyal hesap ID'si.
        limit: 1-50 arası.
    """
    plat = _resolve_platform(platform)
    if plat is None:
        return {
            "success": False,
            "error": f"Unknown Zernio platform '{platform}'",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }
    try:
        client = get_zernio_client()
        threads = await client.list_dm_threads(
            platform=plat,
            account_id=account_id,
            limit=max(1, min(50, limit)),
        )
        return {"success": True, "count": len(threads), "data": threads}
    except ZernioFeatureNotEnabledError as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "INSUFFICIENT_BALANCE",
            "retryable": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "zernio")}


# ---------------------------------------------------------------------------
# Pause campaign (Meta agent autonomous decision)
# ---------------------------------------------------------------------------


@function_tool
async def pause_zernio_campaign(
    platform: str,
    campaign_id: str,
    reason: str,
) -> dict[str, Any]:
    """Bir reklam kampanyasını otonom karar (CTR<1%, CPL>50, vs.) ile durdurur.

    Args:
        platform: ``meta`` | ``linkedin`` | ``google`` | ``tiktok`` | ``pinterest`` | ``x``.
        campaign_id: Zernio Ads kampanya ID.
        reason: Otonom karar gerekçesi (decisions_log için).
    """
    plat = _resolve_platform(platform)
    if plat is None:
        return {
            "success": False,
            "error": f"Unknown Zernio platform '{platform}'",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }
    try:
        client = get_zernio_client()
        result = await client.pause_campaign(
            platform=plat,
            campaign_id=campaign_id,
            reason=reason,
        )
        return {"success": True, **result}
    except ZernioFeatureNotEnabledError as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "INSUFFICIENT_BALANCE",
            "retryable": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "zernio")}


# ---------------------------------------------------------------------------
# Get campaign metrics
# ---------------------------------------------------------------------------


@function_tool
async def get_zernio_campaign_metrics(
    platform: str,
    campaign_id: str,
) -> dict[str, Any]:
    """Bir reklam kampanyasının canlı metriklerini (CTR, CPC, CPL, spend) getirir."""
    plat = _resolve_platform(platform)
    if plat is None:
        return {
            "success": False,
            "error": f"Unknown Zernio platform '{platform}'",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }
    try:
        client = get_zernio_client()
        metrics = await client.get_campaign_metrics(
            platform=plat, campaign_id=campaign_id
        )
        return {"success": True, **metrics}
    except ZernioFeatureNotEnabledError as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "INSUFFICIENT_BALANCE",
            "retryable": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "zernio")}


# ---------------------------------------------------------------------------
# Account analytics
# ---------------------------------------------------------------------------


@function_tool
async def get_zernio_account_analytics(
    platform: str,
    account_id: str,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Bir hesabın impressions/reach/clicks/CTR analitiklerini çeker.

    Args:
        platform: ``instagram`` | ``facebook`` | ``linkedin`` | ``meta`` | ...
        account_id: Zernio account id.
        since: YYYY-MM-DD (opsiyonel).
        until: YYYY-MM-DD (opsiyonel).
    """
    plat = _resolve_platform(platform)
    if plat is None:
        return {
            "success": False,
            "error": f"Unknown Zernio platform '{platform}'",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }
    try:
        client = get_zernio_client()
        data = await client.get_account_analytics(
            platform=plat, account_id=account_id, since=since, until=until
        )
        return {"success": True, **data}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "zernio")}


__all__ = [
    "send_zernio_dm",
    "list_zernio_dm_threads",
    "pause_zernio_campaign",
    "get_zernio_campaign_metrics",
    "get_zernio_account_analytics",
]
