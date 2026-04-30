"""Zernio unified social media API client tests (TEST-FIRST).

Strategy:
- Mock httpx via monkeypatch
- Cover: send_dm, list_dm_threads, post_create, ads_create_campaign,
  ads_pause_campaign, analytics_get, webhook signature verification
- Add-on guards: ZERNIO_INBOX_ENABLED / ZERNIO_ADS_ENABLED flags
"""
from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infra.errors import ErrorCode, ServiceError, classify_error
from src.infra.zernio_client import (
    ZernioClient,
    ZernioConfig,
    ZernioPlatform,
    ZernioFeatureNotEnabledError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cfg_full() -> ZernioClient:
    return ZernioClient(
        ZernioConfig(
            api_key="zk_fake_token",
            base_url="https://api.zernio.com",
            inbox_enabled=True,
            ads_enabled=True,
            analytics_enabled=True,
        )
    )


@pytest.fixture
def cfg_inbox_only() -> ZernioClient:
    return ZernioClient(
        ZernioConfig(
            api_key="zk_fake_token",
            base_url="https://api.zernio.com",
            inbox_enabled=True,
            ads_enabled=False,
            analytics_enabled=True,
        )
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestZernioConfig:
    def test_strips_trailing_slash(self) -> None:
        c = ZernioConfig(api_key="x", base_url="https://api.zernio.com/")
        assert c.base_url == "https://api.zernio.com"

    def test_requires_api_key(self) -> None:
        with pytest.raises(ValueError):
            ZernioConfig(api_key="", base_url="https://api.zernio.com")

    def test_default_base_url(self) -> None:
        c = ZernioConfig(api_key="x")
        assert c.base_url == "https://api.zernio.com"


class TestZernioPlatformEnum:
    def test_known_platforms_present(self) -> None:
        # The platforms we actually need.
        assert ZernioPlatform.INSTAGRAM.value == "instagram"
        assert ZernioPlatform.FACEBOOK.value == "facebook"
        assert ZernioPlatform.LINKEDIN.value == "linkedin"
        assert ZernioPlatform.WHATSAPP.value == "whatsapp"


# ---------------------------------------------------------------------------
# Auth + URL
# ---------------------------------------------------------------------------


class TestZernioWiring:
    def test_bearer_header(self, cfg_full: ZernioClient) -> None:
        h = cfg_full._headers()
        assert h["Authorization"] == "Bearer zk_fake_token"
        assert h["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# DM operations (Inbox addon)
# ---------------------------------------------------------------------------


class TestSendDM:
    @pytest.mark.asyncio
    async def test_send_dm_calls_correct_endpoint(
        self, cfg_full: ZernioClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"id": "msg_123", "status": "sent"}
        )
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg_full, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.post = AsyncMock(return_value=mock_response)
            result = await cfg_full.send_dm(
                platform=ZernioPlatform.INSTAGRAM,
                account_id="acc_ig_1",
                recipient_id="user_42",
                text="Merhaba!",
            )
            assert result["id"] == "msg_123"
            url = fake_client.post.await_args.args[0]
            assert "/dms" in url or "/messages" in url
            body = fake_client.post.await_args.kwargs["json"]
            assert body["platform"] == "instagram"
            assert body["account_id"] == "acc_ig_1"
            assert body["text"] == "Merhaba!"

    @pytest.mark.asyncio
    async def test_send_dm_rejects_when_inbox_disabled(self) -> None:
        client = ZernioClient(
            ZernioConfig(
                api_key="x",
                base_url="https://api.zernio.com",
                inbox_enabled=False,
            )
        )
        with pytest.raises(ZernioFeatureNotEnabledError) as exc_info:
            await client.send_dm(
                platform=ZernioPlatform.INSTAGRAM,
                account_id="acc",
                recipient_id="u",
                text="hi",
            )
        assert "inbox" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_send_dm_classifies_402_as_insufficient_balance(
        self, cfg_full: ZernioClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.text = "addon not enabled"
        err = httpx.HTTPStatusError(
            "payment required",
            request=httpx.Request("POST", "https://api.zernio.com"),
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=err)
        with patch.object(
            cfg_full, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(ServiceError) as exc_info:
                await cfg_full.send_dm(
                    platform=ZernioPlatform.INSTAGRAM,
                    account_id="acc",
                    recipient_id="u",
                    text="hi",
                )
            assert exc_info.value.status_code == 402
            assert exc_info.value.service == "zernio"


class TestListDMThreads:
    @pytest.mark.asyncio
    async def test_list_threads_returns_data_field(
        self, cfg_full: ZernioClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "data": [{"id": "th_1"}, {"id": "th_2"}],
                "page_info": {"total": 2},
            }
        )
        mock_response.raise_for_status = MagicMock()
        with patch.object(
            cfg_full, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            threads = await cfg_full.list_dm_threads(
                platform=ZernioPlatform.INSTAGRAM, account_id="acc"
            )
            assert len(threads) == 2
            assert threads[0]["id"] == "th_1"


# ---------------------------------------------------------------------------
# Ads operations (Ads addon)
# ---------------------------------------------------------------------------


class TestAds:
    @pytest.mark.asyncio
    async def test_pause_campaign_when_ads_disabled_raises(
        self, cfg_inbox_only: ZernioClient
    ) -> None:
        with pytest.raises(ZernioFeatureNotEnabledError):
            await cfg_inbox_only.pause_campaign(
                platform=ZernioPlatform.META,
                campaign_id="camp_1",
                reason="CTR<1%",
            )

    @pytest.mark.asyncio
    async def test_pause_campaign_passes_reason(
        self, cfg_full: ZernioClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"id": "camp_1", "status": "paused"})
        mock_response.raise_for_status = MagicMock()
        with patch.object(
            cfg_full, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.post = AsyncMock(return_value=mock_response)
            result = await cfg_full.pause_campaign(
                platform=ZernioPlatform.META,
                campaign_id="camp_1",
                reason="CTR<1%",
            )
            assert result["status"] == "paused"
            body = fake_client.post.await_args.kwargs["json"]
            assert body["reason"] == "CTR<1%"


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    @pytest.mark.asyncio
    async def test_get_account_analytics(self, cfg_full: ZernioClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "account_id": "acc_1",
                "metrics": {"impressions": 1000, "clicks": 50, "ctr": 0.05},
            }
        )
        mock_response.raise_for_status = MagicMock()
        with patch.object(
            cfg_full, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            data = await cfg_full.get_account_analytics(
                platform=ZernioPlatform.INSTAGRAM,
                account_id="acc_1",
            )
            assert data["metrics"]["clicks"] == 50


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------


class TestWebhookSignature:
    def test_valid_signature_passes(self, cfg_full: ZernioClient) -> None:
        secret = "shared-webhook-secret"
        body = b'{"event":"message.received","data":{}}'
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        signature_header = f"sha256={digest}"
        assert cfg_full.verify_webhook_signature(body, signature_header, secret)

    def test_invalid_signature_fails(self, cfg_full: ZernioClient) -> None:
        body = b'{"event":"x"}'
        assert not cfg_full.verify_webhook_signature(
            body, "sha256=deadbeef", "shared-secret"
        )

    def test_missing_signature_fails(self, cfg_full: ZernioClient) -> None:
        assert not cfg_full.verify_webhook_signature(b"{}", "", "secret")
        assert not cfg_full.verify_webhook_signature(b"{}", None, "secret")


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestZernioErrorClassification:
    def test_402_is_insufficient_balance(self) -> None:
        err = ServiceError("addon", status_code=402, service="zernio")
        result = classify_error(err, "zernio")
        assert result["error_code"] == ErrorCode.INSUFFICIENT_BALANCE

    def test_429_retryable(self) -> None:
        err = ServiceError("rl", status_code=429, service="zernio")
        result = classify_error(err, "zernio")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True
