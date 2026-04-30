"""Pydantic models for Sales — schema mapping smoke tests.

These tests guard the V2 NocoDB schema mapping. If the schema changes
(``customer_agent/docs/NOCODB-SCHEMA-V2.md``), these tests should be updated
accordingly. Failing here means a column rename or removal that other agents
will hit.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models.sales import (
    AgentHealth,
    AgentHealthStatus,
    Campaign,
    CampaignObjective,
    CampaignPlatform,
    CampaignStatus,
    DailyMetric,
    DecisionLog,
    DecisionOutcome,
    DecisionType,
    HotLeadAlert,
    Lead,
    LeadMessage,
    LeadSource,
    LeadStatus,
    MessageChannel,
    MessageDirection,
    ObjectionCategory,
    ObjectionLog,
)


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------


class TestLeadModel:
    def test_minimal_lead_uses_defaults(self) -> None:
        lead = Lead()
        assert lead.lead_score == 0
        assert lead.lead_status == LeadStatus.COLD
        assert lead.source == LeadSource.MANUAL
        assert lead.consent_status is False
        assert lead.tags == []

    def test_score_clamps_above_max(self) -> None:
        with pytest.raises(ValueError):
            Lead(lead_score=11)

    def test_score_clamps_below_min(self) -> None:
        with pytest.raises(ValueError):
            Lead(lead_score=-1)

    def test_phone_strips_spaces_and_dashes(self) -> None:
        lead = Lead(phone="+90 532 123-4567")
        assert lead.phone == "+905321234567"

    def test_email_lowercased(self) -> None:
        lead = Lead(email="ALI@Example.COM")
        assert lead.email == "ali@example.com"

    def test_unknown_fields_ignored(self) -> None:
        # Tolerant reader: future NocoDB columns shouldn't crash parsing.
        lead = Lead.model_validate(
            {"name": "Ali", "future_column": "value", "another": 42}
        )
        assert lead.name == "Ali"

    def test_lead_score_8_is_hot_threshold(self) -> None:
        # Document the contract used by orchestrator: score 8+ -> notify Seyma
        lead = Lead(lead_score=8)
        assert lead.lead_score >= 8

    def test_full_lead_round_trip(self) -> None:
        lead = Lead(
            name="Slowdays Hotel",
            email="info@slowdays.com",
            phone="+905321234567",
            company="Slowdays Bodrum",
            sector="Otel",
            location="Bodrum",
            lead_score=10,
            lead_status=LeadStatus.HOT,
            source=LeadSource.CLAY,
            consent_status=True,
            consent_source="form_v1",
            consent_recorded_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
            tags=["bodrum", "otel", "vip"],
        )
        dumped = lead.model_dump()
        assert dumped["lead_score"] == 10
        assert "bodrum" in dumped["tags"]


# ---------------------------------------------------------------------------
# LeadMessage
# ---------------------------------------------------------------------------


class TestLeadMessage:
    def test_default_outbound_auto_compliant(self) -> None:
        msg = LeadMessage(body="hello")
        assert msg.direction == MessageDirection.OUTBOUND
        assert msg.cbo_compliant is True
        assert msg.is_auto_generated is False

    def test_channel_enum_accepts_string(self) -> None:
        msg = LeadMessage(body="x", channel="instagram_dm")  # type: ignore[arg-type]
        assert msg.channel == MessageChannel.INSTAGRAM_DM


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


class TestCampaign:
    def test_required_platform_and_name(self) -> None:
        with pytest.raises(ValueError):
            Campaign()  # type: ignore[call-arg]
        c = Campaign(platform=CampaignPlatform.META, name="Q2 Lead Gen")
        assert c.status == CampaignStatus.ACTIVE
        assert c.total_spend_try == 0.0

    def test_objective_optional(self) -> None:
        c = Campaign(platform=CampaignPlatform.LINKEDIN, name="x")
        assert c.objective is None
        c2 = Campaign(
            platform=CampaignPlatform.LINKEDIN,
            name="x",
            objective=CampaignObjective.LEAD_GENERATION,
        )
        assert c2.objective == CampaignObjective.LEAD_GENERATION


# ---------------------------------------------------------------------------
# DailyMetric
# ---------------------------------------------------------------------------


class TestDailyMetric:
    def test_zero_defaults(self) -> None:
        m = DailyMetric(date="2026-04-30", channel="meta")
        assert m.impressions == 0
        assert m.cac_try is None  # nullable computed field
        assert m.pipeline_value_try == 0.0


# ---------------------------------------------------------------------------
# DecisionLog
# ---------------------------------------------------------------------------


class TestDecisionLog:
    def test_required_fields(self) -> None:
        d = DecisionLog(
            timestamp=datetime(2026, 4, 30, 12, tzinfo=timezone.utc),
            agent_name="meta_agent",
            decision_type=DecisionType.PAUSE_CAMPAIGN,
            target_entity="campaign#123",
            reason="CTR<1% over 6h",
        )
        assert d.outcome == DecisionOutcome.APPLIED
        assert d.human_required is False


# ---------------------------------------------------------------------------
# ObjectionLog
# ---------------------------------------------------------------------------


class TestObjectionLog:
    def test_default_category_other(self) -> None:
        o = ObjectionLog(objection_text="pahalı geliyor")
        assert o.objection_category == ObjectionCategory.OTHER
        assert o.outcome == "pending"


# ---------------------------------------------------------------------------
# AgentHealth
# ---------------------------------------------------------------------------


class TestAgentHealth:
    def test_defaults(self) -> None:
        h = AgentHealth(agent_name="clay_agent")
        assert h.status == AgentHealthStatus.HEALTHY
        assert h.total_runs_today == 0


# ---------------------------------------------------------------------------
# HotLeadAlert
# ---------------------------------------------------------------------------


class TestHotLeadAlert:
    def test_required_fields(self) -> None:
        alert = HotLeadAlert(
            lead_id=42,
            lead_score=9,
            source=LeadSource.CLAY,
            summary="Bodrum'da otel, web sitesi yok, IG zayıf — 10/10",
            created_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
        )
        assert alert.lead_id == 42
        assert alert.suggested_next_action is None
