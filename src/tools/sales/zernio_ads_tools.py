"""Zernio Ads tools for the Reklam Uzmani (Ads Expert) agent.

Wraps the ``_AdsMixin`` on ``ZernioClient`` as ``@function_tool``s with
Pydantic-validated structured input and dict outputs that all carry a
``success`` flag plus the ``classify_error`` envelope on failure.

Guardrails live here, not in the client:
- Hard cap of ``MAX_DAILY_BUDGET_USD`` on any create/boost call so a
  hallucinated decimal point cannot empty the ad account.
- Whitelisted ``goal`` values (Zernio rejects others server-side, but
  we fail-fast with a localized message).
- ``budget_amount`` must be >= 1 (TikTok=20, Pinterest=5 are still
  validated server-side — we only enforce the global floor).
"""
from __future__ import annotations

from typing import Any

from agents import function_tool
from pydantic import BaseModel, Field

from src.infra.errors import ErrorCode, classify_error


MAX_DAILY_BUDGET_USD = 200.0
MIN_BUDGET_USD = 1.0
SUPPORTED_GOALS = (
    "engagement",
    "traffic",
    "awareness",
    "video_views",
    "lead_generation",
    "conversions",
    "app_promotion",
)


def _get_client():
    from src.infra.zernio import get_zernio_client

    return get_zernio_client()


def _invalid(message_tr: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "error_code": ErrorCode.INVALID_INPUT.value,
        "service": "zernio",
        "retryable": False,
        "user_message_tr": message_tr,
    }


def _validate_budget(amount: float, budget_type: str = "daily") -> dict[str, Any] | None:
    if amount < MIN_BUDGET_USD:
        return _invalid(
            f"Butce cok dusuk (min ${MIN_BUDGET_USD}).",
            f"budget below floor: {amount}",
        )
    if budget_type == "daily" and amount > MAX_DAILY_BUDGET_USD:
        return _invalid(
            f"Gunluk butce ust sinirini astiniz (${MAX_DAILY_BUDGET_USD}).",
            f"daily budget over cap: {amount}",
        )
    return None


def _validate_goal(goal: str) -> dict[str, Any] | None:
    if goal not in SUPPORTED_GOALS:
        return _invalid(
            f"Gecersiz reklam hedefi: {goal}.",
            f"goal not in {SUPPORTED_GOALS}",
        )
    return None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TargetAudience(BaseModel):
    """Targeting payload mirroring Zernio's ``targeting`` schema."""

    age_min: int | None = Field(default=None, ge=13, le=65)
    age_max: int | None = Field(default=None, ge=13, le=65)
    countries: list[str] | None = None
    interests: list[dict[str, str]] | None = None

    def to_payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.age_min is not None:
            out["ageMin"] = self.age_min
        if self.age_max is not None:
            out["ageMax"] = self.age_max
        if self.countries:
            out["countries"] = self.countries
        if self.interests:
            out["interests"] = self.interests
        return out


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


async def _list_campaigns_impl(
    platform: str | None = None,
    status: str | None = None,
    ad_account_id: str | None = None,
    account_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    try:
        client = _get_client()
        data = await client.list_campaigns(
            platform=platform,
            status=status,
            ad_account_id=ad_account_id,
            account_id=account_id,
            limit=limit,
        )
        return {
            "success": True,
            "campaigns": data.get("campaigns", []),
            "count": len(data.get("campaigns", [])),
            "pagination": data.get("pagination"),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _get_campaign_impl(campaign_id: str, platform: str | None = None) -> dict[str, Any]:
    if not campaign_id:
        return _invalid("campaign_id zorunlu.", "campaign_id is required")
    try:
        client = _get_client()
        campaign = await client.get_campaign(campaign_id, platform=platform)
        if not campaign:
            return {
                "success": False,
                "error": f"campaign {campaign_id} not found",
                "error_code": ErrorCode.NOT_FOUND.value,
                "service": "zernio",
                "retryable": False,
                "user_message_tr": "Kampanya bulunamadi.",
            }
        return {"success": True, "campaign": campaign}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _create_campaign_impl(
    account_id: str,
    ad_account_id: str,
    name: str,
    goal: str,
    budget_amount: float,
    body: str,
    budget_type: str = "daily",
    headline: str | None = None,
    link_url: str | None = None,
    image_url: str | None = None,
    call_to_action: str | None = None,
    countries: list[str] | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    audience_id: str | None = None,
) -> dict[str, Any]:
    if err := _validate_goal(goal):
        return err
    if err := _validate_budget(budget_amount, budget_type):
        return err
    if not name or not name.strip():
        return _invalid("Kampanya adi zorunlu.", "name required")
    try:
        client = _get_client()
        data = await client.create_campaign(
            account_id=account_id,
            ad_account_id=ad_account_id,
            name=name.strip(),
            goal=goal,
            budget_amount=budget_amount,
            budget_type=budget_type,
            body=body,
            headline=headline,
            link_url=link_url,
            image_url=image_url,
            call_to_action=call_to_action,
            countries=countries,
            age_min=age_min,
            age_max=age_max,
            audience_id=audience_id,
        )
        return {"success": True, "ad": data.get("ad"), "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _update_campaign_impl(
    campaign_id: str,
    budget_amount: float,
    platform: str = "facebook",
    budget_type: str = "daily",
) -> dict[str, Any]:
    if not campaign_id:
        return _invalid("campaign_id zorunlu.", "campaign_id is required")
    if err := _validate_budget(budget_amount, budget_type):
        return err
    try:
        client = _get_client()
        data = await client.update_campaign(
            campaign_id,
            platform=platform,
            budget_amount=budget_amount,
            budget_type=budget_type,
        )
        return {"success": True, "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _pause_campaign_impl(campaign_id: str, platform: str = "facebook") -> dict[str, Any]:
    if not campaign_id:
        return _invalid("campaign_id zorunlu.", "campaign_id is required")
    try:
        client = _get_client()
        data = await client.pause_campaign(campaign_id, platform=platform)
        return {"success": True, "updated": data.get("updated", 0), "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _activate_campaign_impl(campaign_id: str, platform: str = "facebook") -> dict[str, Any]:
    if not campaign_id:
        return _invalid("campaign_id zorunlu.", "campaign_id is required")
    try:
        client = _get_client()
        data = await client.activate_campaign(campaign_id, platform=platform)
        return {"success": True, "updated": data.get("updated", 0), "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _boost_post_impl(
    account_id: str,
    ad_account_id: str,
    name: str,
    budget_amount: float,
    post_id: str | None = None,
    platform_post_id: str | None = None,
    duration_days: int | None = 7,
    goal: str = "engagement",
    budget_type: str = "daily",
    age_min: int | None = None,
    age_max: int | None = None,
    countries: list[str] | None = None,
    interests: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if not (post_id or platform_post_id):
        return _invalid(
            "post_id ya da platform_post_id gerekli.",
            "post_id or platform_post_id required",
        )
    if err := _validate_goal(goal):
        return err
    if err := _validate_budget(budget_amount, budget_type):
        return err
    target = TargetAudience(
        age_min=age_min,
        age_max=age_max,
        countries=countries,
        interests=interests,
    ).to_payload()
    try:
        client = _get_client()
        data = await client.boost_post(
            account_id=account_id,
            ad_account_id=ad_account_id,
            name=name,
            budget_amount=budget_amount,
            goal=goal,
            budget_type=budget_type,
            post_id=post_id,
            platform_post_id=platform_post_id,
            duration_days=duration_days,
            target_audience=target or None,
        )
        return {"success": True, "ad": data.get("ad"), "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _list_ad_sets_impl(
    platform: str | None = None,
    ad_account_id: str | None = None,
    account_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    try:
        client = _get_client()
        data = await client.list_ad_sets(
            platform=platform,
            ad_account_id=ad_account_id,
            account_id=account_id,
            status=status,
            limit=limit,
        )
        return {
            "success": True,
            "ad_sets": data.get("adSets", []),
            "count": len(data.get("adSets", [])),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _list_ads_impl(
    campaign_id: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    try:
        client = _get_client()
        data = await client.list_ads(
            campaign_id=campaign_id,
            platform=platform,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return {
            "success": True,
            "ads": data.get("ads", []),
            "count": len(data.get("ads", [])),
            "pagination": data.get("pagination"),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _get_ad_insights_impl(
    ad_id: str | None = None,
    campaign_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    breakdowns: list[str] | None = None,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    if not (ad_id or campaign_id):
        return _invalid(
            "ad_id ya da campaign_id gerekli.",
            "ad_id or campaign_id required",
        )
    try:
        client = _get_client()
        data = await client.get_ad_insights(
            ad_id=ad_id,
            campaign_id=campaign_id,
            date_from=date_from,
            date_to=date_to,
            breakdowns=breakdowns,
            metrics=metrics,
        )
        return {"success": True, "insights": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _list_audiences_impl(
    account_id: str, ad_account_id: str, platform: str | None = None
) -> dict[str, Any]:
    try:
        client = _get_client()
        data = await client.list_audiences(
            account_id=account_id, ad_account_id=ad_account_id, platform=platform
        )
        return {
            "success": True,
            "audiences": data.get("audiences", []),
            "count": len(data.get("audiences", [])),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _create_custom_audience_impl(
    account_id: str,
    ad_account_id: str,
    name: str,
    audience_type: str = "customer_list",
    description: str | None = None,
    pixel_id: str | None = None,
    retention_days: int | None = None,
    source_audience_id: str | None = None,
    country: str | None = None,
    ratio: float | None = None,
) -> dict[str, Any]:
    if audience_type not in ("customer_list", "website", "lookalike"):
        return _invalid(
            "Gecersiz audience_type.",
            "audience_type must be customer_list|website|lookalike",
        )
    if audience_type == "website" and not (pixel_id and retention_days):
        return _invalid(
            "Website audience icin pixel_id ve retention_days gerekli.",
            "website audience requires pixel_id + retention_days",
        )
    if audience_type == "lookalike" and not (source_audience_id and country and ratio is not None):
        return _invalid(
            "Lookalike audience icin source_audience_id, country, ratio gerekli.",
            "lookalike audience requires source_audience_id, country, ratio",
        )
    try:
        client = _get_client()
        data = await client.create_custom_audience(
            account_id=account_id,
            ad_account_id=ad_account_id,
            name=name,
            audience_type=audience_type,
            description=description,
            pixel_id=pixel_id,
            retention_days=retention_days,
            source_audience_id=source_audience_id,
            country=country,
            ratio=ratio,
        )
        return {"success": True, "audience": data.get("audience"), "raw": data}
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _list_ad_accounts_impl(account_id: str) -> dict[str, Any]:
    if not account_id:
        return _invalid("account_id zorunlu.", "account_id is required")
    try:
        client = _get_client()
        data = await client.list_ad_accounts(account_id)
        return {
            "success": True,
            "accounts": data.get("accounts", []),
            "count": len(data.get("accounts", [])),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _daily_ads_report_impl(
    platform: str | None = None,
    ad_account_id: str | None = None,
    account_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Roll active campaigns up into a single spend/CTR/CPL digest.

    Used by the ``daily_report`` agent action — single Zernio call (campaigns
    list already carries summed metrics), then we apply a Turkish-friendly
    formatting pass client-side.
    """
    try:
        client = _get_client()
        data = await client.list_campaigns(
            platform=platform,
            ad_account_id=ad_account_id,
            account_id=account_id,
            status="active",
            limit=100,
        )
    except Exception as exc:
        return classify_error(exc, "zernio")

    totals = {"spend": 0.0, "impressions": 0, "clicks": 0, "leads": 0, "conversions": 0}
    rows: list[dict[str, Any]] = []
    for camp in data.get("campaigns", []):
        metrics = camp.get("metrics") or {}
        spend = float(metrics.get("spend", 0) or 0)
        impressions = int(metrics.get("impressions", 0) or 0)
        clicks = int(metrics.get("clicks", 0) or 0)
        leads = int(metrics.get("leads", 0) or 0)
        conversions = int(metrics.get("conversions", 0) or 0)
        totals["spend"] += spend
        totals["impressions"] += impressions
        totals["clicks"] += clicks
        totals["leads"] += leads
        totals["conversions"] += conversions
        ctr = (clicks / impressions * 100) if impressions else 0.0
        cpl = (spend / leads) if leads else None
        rows.append(
            {
                "campaign_id": camp.get("platformCampaignId"),
                "name": camp.get("campaignName"),
                "platform": camp.get("platform"),
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "leads": leads,
                "ctr_pct": round(ctr, 2),
                "cpl": round(cpl, 2) if cpl is not None else None,
            }
        )
    overall_ctr = (totals["clicks"] / totals["impressions"] * 100) if totals["impressions"] else 0.0
    overall_cpl = (totals["spend"] / totals["leads"]) if totals["leads"] else None
    return {
        "success": True,
        "active_campaigns": len(rows),
        "totals": {
            "spend": round(totals["spend"], 2),
            "impressions": totals["impressions"],
            "clicks": totals["clicks"],
            "leads": totals["leads"],
            "ctr_pct": round(overall_ctr, 2),
            "cpl": round(overall_cpl, 2) if overall_cpl is not None else None,
        },
        "campaigns": rows,
        "date_from": date_from,
        "date_to": date_to,
    }


# ---------------------------------------------------------------------------
# function_tool wrappers
# ---------------------------------------------------------------------------


list_ad_campaigns = function_tool(
    name_override="list_ad_campaigns",
    description_override=(
        "List Zernio ad campaigns (paginated, with rolled-up metrics). "
        "Args: platform?, status? (active|paused|...), ad_account_id?, account_id?, limit (default 20)."
    ),
    strict_mode=False,
)(_list_campaigns_impl)

get_ad_campaign = function_tool(
    name_override="get_ad_campaign",
    description_override="Get one campaign by platformCampaignId. Args: campaign_id, platform?",
    strict_mode=False,
)(_get_campaign_impl)

create_ad_campaign = function_tool(
    name_override="create_ad_campaign",
    description_override=(
        "Create a Zernio ad campaign (POST /v1/ads/create). Materializes the full "
        "platform hierarchy (campaign + ad set + ad). Required: account_id, ad_account_id, "
        "name, goal (engagement|traffic|awareness|video_views|lead_generation|conversions|app_promotion), "
        "budget_amount (USD, daily<=200), body. Optional: headline, link_url, image_url, call_to_action, "
        "countries[], age_min, age_max, audience_id."
    ),
    strict_mode=False,
)(_create_campaign_impl)

update_ad_campaign = function_tool(
    name_override="update_ad_campaign",
    description_override=(
        "Update CBO campaign budget (Meta-only). Args: campaign_id, budget_amount, "
        "platform=facebook, budget_type=daily."
    ),
    strict_mode=False,
)(_update_campaign_impl)

pause_ad_campaign = function_tool(
    name_override="pause_ad_campaign",
    description_override="Pause every ad in a campaign. Args: campaign_id, platform=facebook.",
    strict_mode=False,
)(_pause_campaign_impl)

activate_ad_campaign = function_tool(
    name_override="activate_ad_campaign",
    description_override="Resume a paused campaign. Args: campaign_id, platform=facebook.",
    strict_mode=False,
)(_activate_campaign_impl)

boost_post = function_tool(
    name_override="boost_post",
    description_override=(
        "Boost an existing organic post into a paid ad. Required: account_id, ad_account_id, "
        "name, budget_amount, and either post_id (Zernio _id) or platform_post_id. "
        "Optional: duration_days (default 7), goal (default engagement), age_min, age_max, "
        "countries[], interests[]."
    ),
    strict_mode=False,
)(_boost_post_impl)

list_ad_sets = function_tool(
    name_override="list_ad_sets",
    description_override="List ad sets flattened from the campaign tree. Filters: platform, ad_account_id, account_id, status, limit.",
    strict_mode=False,
)(_list_ad_sets_impl)

list_ads = function_tool(
    name_override="list_ads",
    description_override=(
        "List ads with metrics. Filters: campaign_id, platform, status, date_from, date_to, limit (max 500)."
    ),
    strict_mode=False,
)(_list_ads_impl)

get_ad_insights = function_tool(
    name_override="get_ad_insights",
    description_override=(
        "Performance analytics for a single ad (ad_id) or a whole campaign (campaign_id). "
        "Optional: date_from, date_to (YYYY-MM-DD, max 90 days), breakdowns (age,gender,country,...), "
        "metrics[] (client-side filter)."
    ),
    strict_mode=False,
)(_get_ad_insights_impl)

list_ad_audiences = function_tool(
    name_override="list_ad_audiences",
    description_override="List custom audiences. Required: account_id, ad_account_id. Optional: platform.",
    strict_mode=False,
)(_list_audiences_impl)

create_custom_audience = function_tool(
    name_override="create_custom_audience",
    description_override=(
        "Create a Meta custom audience. Required: account_id, ad_account_id, name, "
        "audience_type (customer_list|website|lookalike). Website requires pixel_id + retention_days; "
        "lookalike requires source_audience_id + country + ratio (0.01-0.20)."
    ),
    strict_mode=False,
)(_create_custom_audience_impl)

list_ad_accounts = function_tool(
    name_override="list_ad_accounts",
    description_override="List platform ad accounts (act_xxx) for a Zernio social account. Args: account_id.",
    strict_mode=False,
)(_list_ad_accounts_impl)

daily_ads_report = function_tool(
    name_override="daily_ads_report",
    description_override=(
        "Roll active campaigns up into a single spend/CTR/CPL digest. Optional filters: "
        "platform, ad_account_id, account_id, date_from, date_to."
    ),
    strict_mode=False,
)(_daily_ads_report_impl)


def get_zernio_ads_tools() -> list:
    """All Zernio Ads tools for the Reklam Uzmani Ads Expert agent."""
    return [
        list_ad_campaigns,
        get_ad_campaign,
        create_ad_campaign,
        update_ad_campaign,
        pause_ad_campaign,
        activate_ad_campaign,
        boost_post,
        list_ad_sets,
        list_ads,
        get_ad_insights,
        list_ad_audiences,
        create_custom_audience,
        list_ad_accounts,
        daily_ads_report,
    ]


__all__ = [
    "get_zernio_ads_tools",
    "list_ad_campaigns",
    "get_ad_campaign",
    "create_ad_campaign",
    "update_ad_campaign",
    "pause_ad_campaign",
    "activate_ad_campaign",
    "boost_post",
    "list_ad_sets",
    "list_ads",
    "get_ad_insights",
    "list_ad_audiences",
    "create_custom_audience",
    "list_ad_accounts",
    "daily_ads_report",
    "MAX_DAILY_BUDGET_USD",
    "TargetAudience",
    "_list_campaigns_impl",
    "_get_campaign_impl",
    "_create_campaign_impl",
    "_update_campaign_impl",
    "_pause_campaign_impl",
    "_activate_campaign_impl",
    "_boost_post_impl",
    "_list_ad_sets_impl",
    "_list_ads_impl",
    "_get_ad_insights_impl",
    "_list_audiences_impl",
    "_create_custom_audience_impl",
    "_list_ad_accounts_impl",
    "_daily_ads_report_impl",
    "_get_client",
]
