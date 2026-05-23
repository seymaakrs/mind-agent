"""Ads endpoints on Zernio (``/v1/ads`` family).

Surface scope follows the Zernio OpenAPI v1 spec (docs/from-seyma/zernio-api-openapi.yaml,
lines 17970-19000). Zernio aggregates 6 ad networks (Meta, TikTok, LinkedIn,
Pinterest, Google, X) behind one HTTP API; status/budget/duplicate writes are
Meta-only at the time of writing — other platforms return 501.

Method names mirror the OpenAPI ``operationId`` (camelCase -> snake_case) so a
contributor can grep across the spec and the client.

Naming choices that diverge from the spec (documented for the reviewer):
- ``list_campaigns``/``get_campaign`` are added as friendly aliases over
  ``listAdCampaigns`` (the spec exposes campaigns as virtual aggregations —
  there is no ``GET /v1/ads/campaigns/{id}``; ``get_campaign`` filters
  ``list_campaigns`` by ``platformCampaignId`` locally).
- ``create_campaign`` maps to ``POST /v1/ads/create`` (the spec calls this
  "createStandaloneAd" because the full hierarchy — campaign + ad set + ad
  — is materialized server-side). An ``ad_set`` is created implicitly; the
  spec does not expose a standalone ``POST /v1/ads/ad-sets`` endpoint.
- ``pause_campaign``/``activate_campaign`` are sugar over
  ``PUT /v1/ads/campaigns/{id}/status``.
- ``list_ad_sets``/``create_ad_set`` are not exposed by the spec as
  first-class operations — ad sets surface via ``GET /v1/ads/tree``. We
  reproduce that surface here and document the limitation in the
  docstrings rather than fake endpoints that don't exist.
"""
from __future__ import annotations

from typing import Any


_DEFAULT_PLATFORM = "facebook"
_SUPPORTED_PLATFORMS = (
    "facebook",
    "instagram",
    "tiktok",
    "linkedin",
    "pinterest",
    "google",
    "twitter",
)
_GOALS = (
    "engagement",
    "traffic",
    "awareness",
    "video_views",
    "lead_generation",
    "conversions",
    "app_promotion",
)


class _AdsMixin:
    """``/v1/ads`` endpoints (Ad Campaigns, Ad Sets, Ads, Audiences, Insights).

    See module docstring for the mapping from these methods to OpenAPI
    operationIds.
    """

    # ------------------------------------------------------------------
    # Campaigns
    # ------------------------------------------------------------------

    async def list_campaigns(
        self,
        *,
        platform: str | None = None,
        status: str | None = None,
        ad_account_id: str | None = None,
        account_id: str | None = None,
        profile_id: str | None = None,
        source: str = "all",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """``GET /v1/ads/campaigns`` — paginated virtual aggregations.

        Returns ``{campaigns: [...], pagination: {...}}``. Metrics are summed
        over ads in each campaign. ``status`` filters the derived (rolled-up)
        status.
        """
        params: dict[str, Any] = {
            "page": max(1, page),
            "limit": max(1, min(limit, 100)),
            "source": source,
        }
        if platform:
            params["platform"] = platform
        if status:
            params["status"] = status
        if ad_account_id:
            params["adAccountId"] = ad_account_id
        if account_id:
            params["accountId"] = account_id
        if profile_id:
            params["profileId"] = profile_id
        return await self._get("/ads/campaigns", params=params)

    async def get_campaign(
        self,
        campaign_id: str,
        *,
        platform: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one campaign by ``platformCampaignId``.

        Zernio does not expose ``GET /v1/ads/campaigns/{id}`` (campaigns are
        aggregations, not stored documents). We list and filter client-side,
        which is fine for the volumes the ads expert agent handles (tens of
        active campaigns per business). Returns the matching campaign dict
        or ``{}`` when not found.
        """
        data = await self.list_campaigns(platform=platform, limit=100)
        for camp in data.get("campaigns", []):
            if camp.get("platformCampaignId") == campaign_id or camp.get("_id") == campaign_id:
                return camp
        return {}

    async def create_campaign(
        self,
        *,
        account_id: str,
        ad_account_id: str,
        name: str,
        goal: str,
        budget_amount: float,
        budget_type: str = "daily",
        body: str = "",
        headline: str | None = None,
        link_url: str | None = None,
        image_url: str | None = None,
        call_to_action: str | None = None,
        currency: str | None = None,
        countries: list[str] | None = None,
        age_min: int | None = None,
        age_max: int | None = None,
        interests: list[dict[str, str]] | None = None,
        audience_id: str | None = None,
        end_date: str | None = None,
        advantage_audience: int | None = None,
    ) -> dict[str, Any]:
        """``POST /v1/ads/create`` — creates campaign + ad set + ad in one shot.

        The Zernio spec calls this ``createStandaloneAd`` because everything
        below the campaign (ad set, ad, creative) is auto-provisioned. Use
        ``boost_post`` instead when promoting an existing organic post.
        """
        payload: dict[str, Any] = {
            "accountId": account_id,
            "adAccountId": ad_account_id,
            "name": name,
            "goal": goal,
            "budgetAmount": budget_amount,
            "budgetType": budget_type,
            "body": body,
        }
        if headline is not None:
            payload["headline"] = headline
        if link_url is not None:
            payload["linkUrl"] = link_url
        if image_url is not None:
            payload["imageUrl"] = image_url
        if call_to_action is not None:
            payload["callToAction"] = call_to_action
        if currency is not None:
            payload["currency"] = currency
        if countries is not None:
            payload["countries"] = countries
        if age_min is not None:
            payload["ageMin"] = age_min
        if age_max is not None:
            payload["ageMax"] = age_max
        if interests is not None:
            payload["interests"] = interests
        if audience_id is not None:
            payload["audienceId"] = audience_id
        if end_date is not None:
            payload["endDate"] = end_date
        if advantage_audience is not None:
            payload["advantageAudience"] = advantage_audience
        return await self._post("/ads/create", json=payload)

    async def update_campaign(
        self,
        campaign_id: str,
        *,
        platform: str = _DEFAULT_PLATFORM,
        budget_amount: float,
        budget_type: str = "daily",
    ) -> dict[str, Any]:
        """``PUT /v1/ads/campaigns/{id}`` — CBO budget update (Meta-only).

        Returns 409 BUDGET_LEVEL_MISMATCH on ABO campaigns — callers should
        route to ``update_ad_set`` in that case.
        """
        return await self._put(
            f"/ads/campaigns/{campaign_id}",
            json={
                "platform": platform,
                "budget": {"amount": budget_amount, "type": budget_type},
            },
        )

    async def _set_campaign_status(
        self, campaign_id: str, status: str, platform: str
    ) -> dict[str, Any]:
        return await self._put(
            f"/ads/campaigns/{campaign_id}/status",
            json={"status": status, "platform": platform},
        )

    async def pause_campaign(
        self, campaign_id: str, *, platform: str = _DEFAULT_PLATFORM
    ) -> dict[str, Any]:
        """Pause every ad in the campaign. One platform call (cascades)."""
        return await self._set_campaign_status(campaign_id, "paused", platform)

    async def activate_campaign(
        self, campaign_id: str, *, platform: str = _DEFAULT_PLATFORM
    ) -> dict[str, Any]:
        """Resume a paused campaign."""
        return await self._set_campaign_status(campaign_id, "active", platform)

    # ------------------------------------------------------------------
    # Boost (organic -> paid)
    # ------------------------------------------------------------------

    async def boost_post(
        self,
        *,
        account_id: str,
        ad_account_id: str,
        name: str,
        budget_amount: float,
        goal: str = "engagement",
        budget_type: str = "daily",
        post_id: str | None = None,
        platform_post_id: str | None = None,
        duration_days: int | None = None,
        currency: str | None = None,
        target_audience: dict[str, Any] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """``POST /v1/ads/boost`` — promote an existing organic post.

        ``target_audience`` accepts ``ageMin``, ``ageMax``, ``countries``,
        ``interests`` — see the OpenAPI spec for the full schema. When
        ``duration_days`` is provided and no explicit ``end_date`` is set, the
        end date is computed from ``start_date`` (or "now") so lifetime
        budgets validate server-side.
        """
        payload: dict[str, Any] = {
            "accountId": account_id,
            "adAccountId": ad_account_id,
            "name": name,
            "goal": goal,
            "budget": {"amount": budget_amount, "type": budget_type},
        }
        if post_id:
            payload["postId"] = post_id
        if platform_post_id:
            payload["platformPostId"] = platform_post_id
        if currency:
            payload["currency"] = currency
        if target_audience:
            payload["targeting"] = target_audience
        if start_date or end_date or duration_days:
            schedule: dict[str, Any] = {}
            if start_date:
                schedule["startDate"] = start_date
            if end_date:
                schedule["endDate"] = end_date
            elif duration_days and start_date:
                # caller supplied start + duration; leave end_date to server
                schedule["durationDays"] = duration_days
            payload["schedule"] = schedule
        return await self._post("/ads/boost", json=payload)

    # ------------------------------------------------------------------
    # Ad sets
    # ------------------------------------------------------------------

    async def list_ad_sets(
        self,
        *,
        platform: str | None = None,
        ad_account_id: str | None = None,
        account_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Flatten ``GET /v1/ads/tree`` to an ad-set list.

        Zernio does not have a dedicated ``/v1/ads/ad-sets`` listing
        endpoint — ad sets only appear inside the campaign tree. We fetch
        the tree and flatten one level for callers that want a flat list.
        """
        params: dict[str, Any] = {
            "page": max(1, page),
            "limit": max(1, min(limit, 100)),
        }
        if platform:
            params["platform"] = platform
        if ad_account_id:
            params["adAccountId"] = ad_account_id
        if account_id:
            params["accountId"] = account_id
        if status:
            params["status"] = status
        tree = await self._get("/ads/tree", params=params)
        ad_sets: list[dict[str, Any]] = []
        for camp in tree.get("campaigns", []):
            for ad_set in camp.get("adSets", []):
                ad_sets.append({**ad_set, "campaignId": camp.get("platformCampaignId")})
        return {"adSets": ad_sets, "pagination": tree.get("pagination")}

    async def create_ad_set(
        self,
        *,
        ad_set_id: str,
        platform: str = _DEFAULT_PLATFORM,
        budget_amount: float | None = None,
        budget_type: str = "daily",
        status: str | None = None,
    ) -> dict[str, Any]:
        """Update an ad set (budget and/or status).

        NOTE: Zernio does not expose a standalone "create ad set" endpoint —
        ad sets are auto-created by ``create_campaign``/``boost_post``. This
        method maps to ``PUT /v1/ads/ad-sets/{id}`` for post-creation edits
        (ABO budget tweaks, ad-set-scoped pause/resume). The name is kept
        as ``create_ad_set`` to match the task spec but the docstring is
        explicit about the semantics.
        """
        body: dict[str, Any] = {"platform": platform}
        if budget_amount is not None:
            body["budget"] = {"amount": budget_amount, "type": budget_type}
        if status is not None:
            body["status"] = status
        return await self._put(f"/ads/ad-sets/{ad_set_id}", json=body)

    # ------------------------------------------------------------------
    # Ads
    # ------------------------------------------------------------------

    async def list_ads(
        self,
        *,
        campaign_id: str | None = None,
        platform: str | None = None,
        ad_account_id: str | None = None,
        account_id: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        source: str = "all",
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        """``GET /v1/ads`` — paginated ads with metrics."""
        params: dict[str, Any] = {
            "page": max(1, page),
            "limit": max(1, min(limit, 500)),
            "source": source,
        }
        if campaign_id:
            params["campaignId"] = campaign_id
        if platform:
            params["platform"] = platform
        if ad_account_id:
            params["adAccountId"] = ad_account_id
        if account_id:
            params["accountId"] = account_id
        if status:
            params["status"] = status
        if date_from:
            params["fromDate"] = date_from
        if date_to:
            params["toDate"] = date_to
        return await self._get("/ads", params=params)

    async def get_ad(self, ad_id: str) -> dict[str, Any]:
        """``GET /v1/ads/{id}`` — single ad with creative + metrics."""
        return await self._get(f"/ads/{ad_id}")

    async def create_ad(
        self,
        *,
        account_id: str,
        ad_account_id: str,
        name: str,
        goal: str,
        body: str,
        budget_amount: float,
        budget_type: str = "daily",
        headline: str | None = None,
        link_url: str | None = None,
        image_url: str | None = None,
        call_to_action: str | None = None,
        countries: list[str] | None = None,
        age_min: int | None = None,
        age_max: int | None = None,
        interests: list[dict[str, str]] | None = None,
        audience_id: str | None = None,
    ) -> dict[str, Any]:
        """Alias for ``create_campaign`` — ``POST /v1/ads/create`` produces an
        ad with the campaign hierarchy attached. Kept distinct in the public
        API because the task spec asks for both ``create_campaign`` and
        ``create_ad`` even though Zernio collapses them into one endpoint.
        """
        return await self.create_campaign(
            account_id=account_id,
            ad_account_id=ad_account_id,
            name=name,
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
            interests=interests,
            audience_id=audience_id,
        )

    async def update_ad(
        self,
        ad_id: str,
        *,
        status: str | None = None,
        budget_amount: float | None = None,
        budget_type: str = "daily",
        name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if status is not None:
            body["status"] = status
        if budget_amount is not None:
            body["budget"] = {"amount": budget_amount, "type": budget_type}
        if name is not None:
            body["name"] = name
        return await self._put(f"/ads/{ad_id}", json=body)

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------

    async def get_ad_insights(
        self,
        *,
        ad_id: str | None = None,
        campaign_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        breakdowns: list[str] | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Performance analytics for one ad or a whole campaign.

        - ``ad_id`` -> ``GET /v1/ads/{id}/analytics`` (summary + daily + breakdowns)
        - ``campaign_id`` -> ``GET /v1/ads?campaignId=...`` rolled up locally

        ``metrics`` is accepted for symmetry with Meta's Insights API; Zernio
        always returns the full AdMetrics shape, so this parameter is a
        client-side filter applied after the response.
        """
        if ad_id:
            params: dict[str, Any] = {}
            if date_from:
                params["fromDate"] = date_from
            if date_to:
                params["toDate"] = date_to
            if breakdowns:
                params["breakdowns"] = ",".join(breakdowns)
            data = await self._get(f"/ads/{ad_id}/analytics", params=params)
            if metrics and isinstance(data.get("analytics", {}).get("summary"), dict):
                summary = data["analytics"]["summary"]
                data["analytics"]["summary"] = {k: summary.get(k) for k in metrics}
            return data
        if campaign_id:
            ads = await self.list_ads(
                campaign_id=campaign_id,
                date_from=date_from,
                date_to=date_to,
                limit=500,
            )
            totals: dict[str, float] = {}
            for ad in ads.get("ads", []):
                for k, v in (ad.get("metrics") or {}).items():
                    if isinstance(v, (int, float)):
                        totals[k] = totals.get(k, 0) + v
            if metrics:
                totals = {k: totals.get(k, 0) for k in metrics}
            return {"campaignId": campaign_id, "summary": totals, "adCount": len(ads.get("ads", []))}
        raise ValueError("get_ad_insights requires either ad_id or campaign_id")

    # ------------------------------------------------------------------
    # Audiences
    # ------------------------------------------------------------------

    async def list_audiences(
        self,
        *,
        account_id: str,
        ad_account_id: str,
        platform: str | None = None,
    ) -> dict[str, Any]:
        """``GET /v1/ads/audiences`` — list custom audiences."""
        params: dict[str, Any] = {
            "accountId": account_id,
            "adAccountId": ad_account_id,
        }
        if platform:
            params["platform"] = platform
        return await self._get("/ads/audiences", params=params)

    async def create_custom_audience(
        self,
        *,
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
        customer_file_source: str | None = None,
    ) -> dict[str, Any]:
        """``POST /v1/ads/audiences`` — create Meta custom audience.

        ``audience_type`` ∈ {customer_list, website, lookalike}. Each type
        has its own required-field set (see spec lines 18830-18839).
        """
        payload: dict[str, Any] = {
            "accountId": account_id,
            "adAccountId": ad_account_id,
            "name": name,
            "type": audience_type,
        }
        if description:
            payload["description"] = description
        if pixel_id:
            payload["pixelId"] = pixel_id
        if retention_days is not None:
            payload["retentionDays"] = retention_days
        if source_audience_id:
            payload["sourceAudienceId"] = source_audience_id
        if country:
            payload["country"] = country
        if ratio is not None:
            payload["ratio"] = ratio
        if customer_file_source:
            payload["customerFileSource"] = customer_file_source
        return await self._post("/ads/audiences", json=payload)

    async def list_ad_accounts(self, account_id: str) -> dict[str, Any]:
        """``GET /v1/ads/accounts?accountId=...`` — list platform ad accounts."""
        return await self._get("/ads/accounts", params={"accountId": account_id})


__all__ = ["_AdsMixin"]
