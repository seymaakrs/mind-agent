"""Tests for Zernio Ads mixin + tools layer.

Covers ``src/infra/zernio/ads.py`` (HTTP shape) and
``src/tools/sales/zernio_ads_tools.py`` (validation + error envelope).
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


def _mock_response(status: int, json_body: Any = None, text_body: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text_body or (str(json_body) if json_body else "")
    resp.json = MagicMock(return_value=json_body if json_body is not None else {})
    return resp


def _patch_async_client(method: str, response: MagicMock):
    return patch.object(
        httpx.AsyncClient, method, new=AsyncMock(return_value=response)
    )


def _client():
    from src.infra.zernio import ZernioClient

    return ZernioClient(
        api_key="sk_test_123",
        account_id="wa_acc_id",
        base_url="https://api.zernio.com/v1",
    )


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------


class TestAdsMixinCampaigns:
    @pytest.mark.asyncio
    async def test_list_campaigns_sends_filters(self):
        client = _client()
        with _patch_async_client(
            "get",
            _mock_response(
                200, {"campaigns": [{"platformCampaignId": "c1"}], "pagination": {}}
            ),
        ) as mock_get:
            data = await client.list_campaigns(
                platform="facebook", status="active", limit=50, ad_account_id="act_1"
            )

        assert data["campaigns"][0]["platformCampaignId"] == "c1"
        params = mock_get.await_args.kwargs["params"]
        assert params["platform"] == "facebook"
        assert params["status"] == "active"
        assert params["limit"] == 50
        assert params["adAccountId"] == "act_1"
        assert params["source"] == "all"
        url = mock_get.await_args.args[0]
        assert url.endswith("/ads/campaigns")

    @pytest.mark.asyncio
    async def test_pause_campaign_puts_status(self):
        client = _client()
        with _patch_async_client(
            "put", _mock_response(200, {"updated": 3})
        ) as mock_put:
            data = await client.pause_campaign("c1", platform="instagram")

        assert data["updated"] == 3
        body = mock_put.await_args.kwargs["json"]
        assert body == {"status": "paused", "platform": "instagram"}
        url = mock_put.await_args.args[0]
        assert url.endswith("/ads/campaigns/c1/status")

    @pytest.mark.asyncio
    async def test_activate_campaign_puts_active(self):
        client = _client()
        with _patch_async_client(
            "put", _mock_response(200, {"updated": 1})
        ) as mock_put:
            await client.activate_campaign("c2")

        body = mock_put.await_args.kwargs["json"]
        assert body["status"] == "active"
        assert body["platform"] == "facebook"

    @pytest.mark.asyncio
    async def test_update_campaign_budget(self):
        client = _client()
        with _patch_async_client(
            "put", _mock_response(200, {"updated": 1, "budgetLevel": "campaign"})
        ) as mock_put:
            await client.update_campaign(
                "c1", platform="facebook", budget_amount=50.0, budget_type="daily"
            )

        body = mock_put.await_args.kwargs["json"]
        assert body["platform"] == "facebook"
        assert body["budget"] == {"amount": 50.0, "type": "daily"}

    @pytest.mark.asyncio
    async def test_create_campaign_posts_to_ads_create(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(201, {"ad": {"_id": "ad1"}})
        ) as mock_post:
            await client.create_campaign(
                account_id="acc1",
                ad_account_id="act_1",
                name="Test",
                goal="traffic",
                budget_amount=20.0,
                body="Click",
                headline="H",
                link_url="https://example.com",
            )

        url = mock_post.await_args.args[0]
        assert url.endswith("/ads/create")
        body = mock_post.await_args.kwargs["json"]
        assert body["accountId"] == "acc1"
        assert body["adAccountId"] == "act_1"
        assert body["goal"] == "traffic"
        assert body["budgetAmount"] == 20.0
        assert body["budgetType"] == "daily"
        assert body["headline"] == "H"
        assert body["linkUrl"] == "https://example.com"


class TestAdsMixinBoostAndAds:
    @pytest.mark.asyncio
    async def test_boost_post_includes_targeting_and_schedule(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(201, {"ad": {"_id": "ad2"}})
        ) as mock_post:
            await client.boost_post(
                account_id="acc1",
                ad_account_id="act_1",
                name="Boost",
                budget_amount=10.0,
                post_id="post123",
                target_audience={"ageMin": 25, "countries": ["TR"]},
                start_date="2026-05-22T00:00:00Z",
                duration_days=7,
            )

        url = mock_post.await_args.args[0]
        assert url.endswith("/ads/boost")
        body = mock_post.await_args.kwargs["json"]
        assert body["postId"] == "post123"
        assert body["budget"] == {"amount": 10.0, "type": "daily"}
        assert body["targeting"] == {"ageMin": 25, "countries": ["TR"]}
        assert body["schedule"]["startDate"] == "2026-05-22T00:00:00Z"

    @pytest.mark.asyncio
    async def test_list_ads_with_campaign_filter(self):
        client = _client()
        with _patch_async_client(
            "get", _mock_response(200, {"ads": [], "pagination": {}})
        ) as mock_get:
            await client.list_ads(campaign_id="c1", platform="facebook", limit=100)

        params = mock_get.await_args.kwargs["params"]
        assert params["campaignId"] == "c1"
        assert params["platform"] == "facebook"
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_get_ad_insights_for_ad(self):
        client = _client()
        payload = {
            "ad": {"id": "ad1"},
            "analytics": {
                "summary": {"spend": 12.5, "impressions": 1000, "clicks": 50},
                "daily": [],
            },
        }
        with _patch_async_client("get", _mock_response(200, payload)) as mock_get:
            data = await client.get_ad_insights(
                ad_id="ad1", date_from="2026-05-01", date_to="2026-05-10"
            )

        url = mock_get.await_args.args[0]
        assert url.endswith("/ads/ad1/analytics")
        params = mock_get.await_args.kwargs["params"]
        assert params["fromDate"] == "2026-05-01"
        assert params["toDate"] == "2026-05-10"
        assert data["analytics"]["summary"]["spend"] == 12.5

    @pytest.mark.asyncio
    async def test_get_ad_insights_for_campaign_rolls_up(self):
        client = _client()
        ads_payload = {
            "ads": [
                {"metrics": {"spend": 5, "clicks": 2}},
                {"metrics": {"spend": 7.5, "clicks": 3}},
            ]
        }
        with _patch_async_client("get", _mock_response(200, ads_payload)):
            data = await client.get_ad_insights(campaign_id="c1")

        assert data["campaignId"] == "c1"
        assert data["summary"]["spend"] == 12.5
        assert data["summary"]["clicks"] == 5
        assert data["adCount"] == 2

    @pytest.mark.asyncio
    async def test_get_ad_insights_requires_id(self):
        client = _client()
        with pytest.raises(ValueError):
            await client.get_ad_insights()


class TestAdsMixinAudiences:
    @pytest.mark.asyncio
    async def test_list_audiences_sends_required_params(self):
        client = _client()
        with _patch_async_client(
            "get", _mock_response(200, {"audiences": []})
        ) as mock_get:
            await client.list_audiences(
                account_id="acc1", ad_account_id="act_1", platform="facebook"
            )

        params = mock_get.await_args.kwargs["params"]
        assert params["accountId"] == "acc1"
        assert params["adAccountId"] == "act_1"
        assert params["platform"] == "facebook"

    @pytest.mark.asyncio
    async def test_create_custom_audience_customer_list(self):
        client = _client()
        with _patch_async_client(
            "post", _mock_response(201, {"audience": {"id": "aud1"}})
        ) as mock_post:
            await client.create_custom_audience(
                account_id="acc1",
                ad_account_id="act_1",
                name="My customers",
                audience_type="customer_list",
                description="VIP",
            )

        body = mock_post.await_args.kwargs["json"]
        assert body["type"] == "customer_list"
        assert body["name"] == "My customers"
        assert body["description"] == "VIP"

    @pytest.mark.asyncio
    async def test_raises_on_4xx(self):
        client = _client()
        with _patch_async_client("get", _mock_response(429, text_body="rate limited")):
            from src.infra.errors import ServiceError

            with pytest.raises(ServiceError) as exc_info:
                await client.list_campaigns()
            assert exc_info.value.status_code == 429
            assert exc_info.value.service == "zernio"


# ---------------------------------------------------------------------------
# Tools layer
# ---------------------------------------------------------------------------


class _FakeClient:
    """Stand-in for ZernioClient that records calls and returns canned responses."""

    def __init__(self, responses: dict[str, Any] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    def _record(self, method, args, kwargs):
        async def _impl():
            self.calls.append((method, {"args": args, **kwargs}))
            resp = self.responses.get(method)
            if isinstance(resp, Exception):
                raise resp
            return resp if resp is not None else {}

        return _impl()

    def __getattr__(self, name):
        def _method(*args, **kwargs):
            return self._record(name, args, kwargs)

        return _method


def _patch_tool_client(fake: _FakeClient):
    return patch(
        "src.tools.sales.zernio_ads_tools._get_client", return_value=fake
    )


class TestToolsHappyPath:
    @pytest.mark.asyncio
    async def test_list_campaigns_tool_returns_count(self):
        from src.tools.sales.zernio_ads_tools import _list_campaigns_impl

        fake = _FakeClient(
            {"list_campaigns": {"campaigns": [{"platformCampaignId": "c1"}], "pagination": {}}}
        )
        with _patch_tool_client(fake):
            out = await _list_campaigns_impl(platform="facebook", limit=10)

        assert out["success"] is True
        assert out["count"] == 1
        assert fake.calls[0][1]["platform"] == "facebook"

    @pytest.mark.asyncio
    async def test_boost_post_tool_happy(self):
        from src.tools.sales.zernio_ads_tools import _boost_post_impl

        fake = _FakeClient({"boost_post": {"ad": {"_id": "ad1"}}})
        with _patch_tool_client(fake):
            out = await _boost_post_impl(
                account_id="acc",
                ad_account_id="act_1",
                name="Boost",
                budget_amount=15.0,
                post_id="p1",
                countries=["TR"],
            )
        assert out["success"] is True
        assert out["ad"] == {"_id": "ad1"}
        assert fake.calls[0][1]["budget_amount"] == 15.0

    @pytest.mark.asyncio
    async def test_create_campaign_tool_happy(self):
        from src.tools.sales.zernio_ads_tools import _create_campaign_impl

        fake = _FakeClient({"create_campaign": {"ad": {"_id": "x"}}})
        with _patch_tool_client(fake):
            out = await _create_campaign_impl(
                account_id="acc",
                ad_account_id="act_1",
                name="Test",
                goal="traffic",
                budget_amount=50.0,
                body="Click",
            )
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_pause_campaign_tool_happy(self):
        from src.tools.sales.zernio_ads_tools import _pause_campaign_impl

        fake = _FakeClient({"pause_campaign": {"updated": 2}})
        with _patch_tool_client(fake):
            out = await _pause_campaign_impl("c1")
        assert out["success"] is True
        assert out["updated"] == 2

    @pytest.mark.asyncio
    async def test_daily_ads_report_aggregates(self):
        from src.tools.sales.zernio_ads_tools import _daily_ads_report_impl

        fake = _FakeClient(
            {
                "list_campaigns": {
                    "campaigns": [
                        {
                            "platformCampaignId": "c1",
                            "campaignName": "C1",
                            "platform": "facebook",
                            "metrics": {
                                "spend": 100,
                                "impressions": 10000,
                                "clicks": 200,
                                "leads": 10,
                            },
                        },
                        {
                            "platformCampaignId": "c2",
                            "campaignName": "C2",
                            "platform": "facebook",
                            "metrics": {
                                "spend": 50,
                                "impressions": 5000,
                                "clicks": 50,
                                "leads": 0,
                            },
                        },
                    ]
                }
            }
        )
        with _patch_tool_client(fake):
            out = await _daily_ads_report_impl()

        assert out["success"] is True
        assert out["active_campaigns"] == 2
        assert out["totals"]["spend"] == 150.0
        assert out["totals"]["impressions"] == 15000
        assert out["totals"]["leads"] == 10
        assert out["totals"]["cpl"] == 15.0
        # c1 has CPL=10, c2 has no leads (cpl=None)
        cpls = {c["campaign_id"]: c["cpl"] for c in out["campaigns"]}
        assert cpls["c1"] == 10.0
        assert cpls["c2"] is None


class TestToolsValidation:
    @pytest.mark.asyncio
    async def test_budget_over_cap_rejected(self):
        from src.tools.sales.zernio_ads_tools import (
            _create_campaign_impl,
            MAX_DAILY_BUDGET_USD,
        )

        out = await _create_campaign_impl(
            account_id="acc",
            ad_account_id="act_1",
            name="Test",
            goal="traffic",
            budget_amount=MAX_DAILY_BUDGET_USD + 50,
            body="x",
        )
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"
        assert "ust sinir" in out["user_message_tr"].lower() or "üst" in out["user_message_tr"].lower()

    @pytest.mark.asyncio
    async def test_budget_below_floor_rejected(self):
        from src.tools.sales.zernio_ads_tools import _create_campaign_impl

        out = await _create_campaign_impl(
            account_id="acc",
            ad_account_id="act_1",
            name="Test",
            goal="traffic",
            budget_amount=0.5,
            body="x",
        )
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_invalid_goal_rejected(self):
        from src.tools.sales.zernio_ads_tools import _create_campaign_impl

        out = await _create_campaign_impl(
            account_id="acc",
            ad_account_id="act_1",
            name="Test",
            goal="world_domination",
            budget_amount=10.0,
            body="x",
        )
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_boost_post_requires_post_id(self):
        from src.tools.sales.zernio_ads_tools import _boost_post_impl

        out = await _boost_post_impl(
            account_id="acc",
            ad_account_id="act_1",
            name="Boost",
            budget_amount=10.0,
        )
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_insights_requires_id(self):
        from src.tools.sales.zernio_ads_tools import _get_ad_insights_impl

        out = await _get_ad_insights_impl()
        assert out["success"] is False
        assert out["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_create_audience_lookalike_requires_fields(self):
        from src.tools.sales.zernio_ads_tools import _create_custom_audience_impl

        out = await _create_custom_audience_impl(
            account_id="acc",
            ad_account_id="act_1",
            name="LL",
            audience_type="lookalike",
        )
        assert out["success"] is False
        assert "lookalike" in out["error"].lower()


class TestToolsErrorMapping:
    @pytest.mark.asyncio
    async def test_rate_limit_classifies_retryable(self):
        from src.infra.errors import ServiceError
        from src.tools.sales.zernio_ads_tools import _list_campaigns_impl

        fake = _FakeClient(
            {"list_campaigns": ServiceError("rate", status_code=429, service="zernio")}
        )
        with _patch_tool_client(fake):
            out = await _list_campaigns_impl()

        assert out["success"] is False
        assert out["error_code"] == "RATE_LIMIT"
        assert out["retryable"] is True

    @pytest.mark.asyncio
    async def test_get_campaign_not_found_returns_envelope(self):
        from src.tools.sales.zernio_ads_tools import _get_campaign_impl

        fake = _FakeClient({"get_campaign": {}})
        with _patch_tool_client(fake):
            out = await _get_campaign_impl("doesnotexist")

        assert out["success"] is False
        assert out["error_code"] == "NOT_FOUND"


class TestToolsRegistry:
    def test_get_zernio_ads_tools_returns_all(self):
        from src.tools.sales.zernio_ads_tools import get_zernio_ads_tools

        tools = get_zernio_ads_tools()
        names = {t.name for t in tools}
        for expected in [
            "list_ad_campaigns",
            "create_ad_campaign",
            "boost_post",
            "pause_ad_campaign",
            "activate_ad_campaign",
            "daily_ads_report",
            "get_ad_insights",
            "list_ad_audiences",
            "create_custom_audience",
        ]:
            assert expected in names
