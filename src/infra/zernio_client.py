"""Zernio unified social media API client.

Zernio (https://zernio.com) provides one REST API for 15 social platforms
(Instagram, Facebook, LinkedIn, WhatsApp, TikTok, X, Threads, YouTube, ...)
covering posting, DM/inbox, analytics, and ads.

This client is a thin async wrapper used by mind-agent sales sub-agents to:
- Send/receive DMs (IG, Facebook, LinkedIn, WhatsApp, ...) via Inbox addon.
- Manage paid ad campaigns (auto-pause, budget changes) via Ads addon.
- Pull unified analytics (impressions/clicks/ctr per platform) for daily reporter.

Add-on guards
-------------
Zernio sells features as $10/mo addons (Inbox, Ads, Analytics). The client
respects feature flags so sales agents never call disabled endpoints.
``ZernioFeatureNotEnabledError`` is raised when a guarded method is called
without the matching flag enabled — this is a programmer error, not a runtime
ServiceError.

Webhook handling
----------------
Zernio signs every webhook payload with HMAC-SHA256.  ``verify_webhook_signature``
guards the FastAPI receiver in mind-agent so we don't process spoofed events.

Authentication: Bearer token in ``Authorization`` header.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx

from src.infra.errors import ServiceError


# ---------------------------------------------------------------------------
# Enums + Errors
# ---------------------------------------------------------------------------


class ZernioPlatform(StrEnum):
    """Subset of Zernio's supported platforms that we use today.

    Add new entries as we expand to more channels.
    """

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    META = "meta"  # Zernio Ads API treats Meta as a single platform
    TIKTOK = "tiktok"
    X = "x"
    THREADS = "threads"


class ZernioFeatureNotEnabledError(RuntimeError):
    """Raised when a guarded method is called without the matching addon enabled.

    Example: ``send_dm`` requires ``inbox_enabled=True`` in ``ZernioConfig``.
    """


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ZernioConfig:
    """Zernio client configuration.

    Args:
        api_key: Bearer token from Zernio dashboard (Settings -> API Keys).
        base_url: Override only for self-hosted/staging.
        inbox_enabled: True if user has the $10/mo Inbox addon active.
        ads_enabled: True if user has the $10/mo Ads addon active.
        analytics_enabled: Analytics is included in any paid plan; default True.
        timeout_seconds: HTTP request timeout.
    """

    api_key: str
    base_url: str = "https://api.zernio.com"
    inbox_enabled: bool = False
    ads_enabled: bool = False
    analytics_enabled: bool = True
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("ZernioConfig.api_key is required")
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ZernioClient:
    """Async Zernio REST client.

    Endpoint conventions documented at https://docs.zernio.com.  We only call
    a small subset; expand as needed.
    """

    def __init__(self, config: ZernioConfig) -> None:
        self.config = config
        self._async_client = httpx.AsyncClient(timeout=config.timeout_seconds)

    # ------------------------------------------------------------------ helpers

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _raise_service_error(
        self, exc: httpx.HTTPStatusError, action: str
    ) -> None:
        status = exc.response.status_code if exc.response is not None else None
        text = exc.response.text if exc.response is not None else str(exc)
        raise ServiceError(
            f"Zernio {action} failed (HTTP {status}): {text}",
            status_code=status,
            service="zernio",
        ) from exc

    # ------------------------------------------------------------------ DMs

    async def send_dm(
        self,
        *,
        platform: ZernioPlatform,
        account_id: str,
        recipient_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a DM through Zernio Inbox addon.

        API docs: https://docs.zernio.com — Inbox API uses
        ``POST /v1/inbox/conversations/{conversationId}/messages`` to reply
        within an existing conversation. When ``thread_id`` is omitted we
        treat the recipient as the conversation key (Zernio resolves it
        per platform); pass ``thread_id`` when you already have it from a
        prior ``message.received`` webhook.

        Raises:
            ZernioFeatureNotEnabledError: if ``inbox_enabled=False``.
            ServiceError: on HTTP/transport errors.
        """
        if not self.config.inbox_enabled:
            raise ZernioFeatureNotEnabledError(
                "Zernio inbox addon is not enabled. Enable it in Zernio dashboard "
                "and set ZERNIO_INBOX_ENABLED=true."
            )

        # Conversation key: prefer the explicit thread_id (returned in webhooks),
        # otherwise pass the recipient_id and Zernio resolves it per platform.
        conversation_key = thread_id or recipient_id

        body: dict[str, Any] = {
            "platform": platform.value,
            "account_id": account_id,
            "recipient_id": recipient_id,
            "text": text,
        }

        try:
            resp = await self._async_client.post(
                self._url(f"/v1/inbox/conversations/{conversation_key}/messages"),
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "send_dm")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Zernio send_dm network error: {exc}",
                status_code=None,
                service="zernio",
            ) from exc

        return resp.json()

    async def list_dm_threads(
        self,
        *,
        platform: ZernioPlatform,
        account_id: str,
        limit: int = 25,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent DM conversations for an account.

        Uses the documented ``GET /v1/inbox/conversations`` endpoint with
        ``platform`` filter.
        """
        if not self.config.inbox_enabled:
            raise ZernioFeatureNotEnabledError(
                "Zernio inbox addon is not enabled."
            )

        params: dict[str, Any] = {
            "platform": platform.value,
            "account_id": account_id,
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor

        try:
            resp = await self._async_client.get(
                self._url("/v1/inbox/conversations"),
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "list_dm_threads")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Zernio list_dm_threads network error: {exc}",
                status_code=None,
                service="zernio",
            ) from exc

        data = resp.json()
        if isinstance(data, dict):
            # Zernio returns either {"data": [...]} or just a list — be tolerant.
            return list(data.get("data", data.get("conversations", [])))
        if isinstance(data, list):
            return data
        return []

    # ------------------------------------------------------------------ Ads

    async def pause_campaign(
        self,
        *,
        platform: ZernioPlatform,
        campaign_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Pause an ad campaign with audit reason.

        Used by autonomous decision rules (CTR<1%, CPL>50, etc.).
        Reason is logged on Zernio and copied into ``decisions_log``.
        """
        if not self.config.ads_enabled:
            raise ZernioFeatureNotEnabledError(
                "Zernio ads addon is not enabled."
            )

        body = {
            "platform": platform.value,
            "campaign_id": campaign_id,
            "action": "pause",
            "reason": reason,
        }
        try:
            resp = await self._async_client.post(
                self._url("/v1/ads/campaigns/actions"),
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "pause_campaign")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Zernio pause_campaign network error: {exc}",
                status_code=None,
                service="zernio",
            ) from exc

        return resp.json()

    async def get_campaign_metrics(
        self,
        *,
        platform: ZernioPlatform,
        campaign_id: str,
    ) -> dict[str, Any]:
        """Read CTR/CPC/CPL/spend for a campaign."""
        if not self.config.ads_enabled:
            raise ZernioFeatureNotEnabledError(
                "Zernio ads addon is not enabled."
            )

        try:
            resp = await self._async_client.get(
                self._url(f"/v1/ads/campaigns/{campaign_id}/metrics"),
                headers=self._headers(),
                params={"platform": platform.value},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "get_campaign_metrics")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Zernio get_campaign_metrics network error: {exc}",
                status_code=None,
                service="zernio",
            ) from exc

        return resp.json()

    # ------------------------------------------------------------------ Analytics

    async def get_account_analytics(
        self,
        *,
        platform: ZernioPlatform,
        account_id: str,
        since: str | None = None,
        until: str | None = None,
    ) -> dict[str, Any]:
        """Fetch impressions/reach/clicks/CTR for an account.

        Time range is YYYY-MM-DD; defaults to last 24h on Zernio side.
        """
        params: dict[str, Any] = {
            "platform": platform.value,
            "account_id": account_id,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        try:
            resp = await self._async_client.get(
                self._url("/v1/analytics/accounts"),
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_service_error(exc, "get_account_analytics")
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Zernio get_account_analytics network error: {exc}",
                status_code=None,
                service="zernio",
            ) from exc

        return resp.json()

    # ------------------------------------------------------------------ Webhook verification

    @staticmethod
    def verify_webhook_signature(
        body: bytes,
        signature_header: str | None,
        webhook_secret: str,
    ) -> bool:
        """Constant-time HMAC-SHA256 verification.

        Zernio sends ``X-Zernio-Signature: sha256=<hexdigest>`` on every webhook.
        Always call this on the raw request body BEFORE parsing JSON.
        """
        if not signature_header or not webhook_secret:
            return False
        if not signature_header.startswith("sha256="):
            return False
        expected = signature_header.split("=", 1)[1]
        actual = hmac.new(
            webhook_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, actual)

    # ------------------------------------------------------------------ Lifecycle

    async def aclose(self) -> None:
        await self._async_client.aclose()


_singleton: ZernioClient | None = None


def get_zernio_client() -> ZernioClient:
    """Process-wide singleton Zernio client built from settings.

    Raises:
        RuntimeError: when ZERNIO_API_KEY is missing. Tools should catch this
            and return a structured error.
    """
    global _singleton
    if _singleton is not None:
        return _singleton

    from src.app.config import get_settings

    s = get_settings()
    if not s.zernio_api_key:
        raise RuntimeError(
            "Zernio is not configured. Set ZERNIO_API_KEY env var."
        )

    _singleton = ZernioClient(
        ZernioConfig(
            api_key=s.zernio_api_key,
            base_url=s.zernio_base_url,
            inbox_enabled=s.zernio_inbox_enabled,
            ads_enabled=s.zernio_ads_enabled,
            analytics_enabled=s.zernio_analytics_enabled,
        )
    )
    return _singleton


def reset_zernio_client() -> None:
    """Reset the singleton — used by tests."""
    global _singleton
    _singleton = None


__all__ = [
    "ZernioClient",
    "ZernioConfig",
    "ZernioPlatform",
    "ZernioFeatureNotEnabledError",
    "get_zernio_client",
    "reset_zernio_client",
]
