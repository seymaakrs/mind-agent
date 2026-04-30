"""Pydantic models for the Customer Agent (Sales) system.

Schema source of truth: ``customer_agent/docs/NOCODB-SCHEMA-V2.md``.
Every column documented there has a matching field below.

Tolerant reader principle:
- All non-essential fields are optional with safe defaults.
- ``model_config = ConfigDict(extra="ignore")`` so future NocoDB columns
  don't crash the parser.
- Validators normalize incoming strings (lowercase enums, stripped phones, etc.)
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums (mirror NocoDB SingleSelect option lists)
# ---------------------------------------------------------------------------


class LeadStatus(StrEnum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CLOSED = "closed"
    LOST = "lost"


class LeadSource(StrEnum):
    META = "meta"
    CLAY = "clay"
    LINKEDIN = "linkedin"
    IG_DM = "ig_dm"
    MANUAL = "manual"
    REFERRAL = "referral"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageChannel(StrEnum):
    META_DM = "meta_dm"
    INSTAGRAM_DM = "instagram_dm"
    LINKEDIN_DM = "linkedin_dm"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    INTERNAL_NOTE = "internal_note"


class CampaignPlatform(StrEnum):
    META = "meta"
    LINKEDIN = "linkedin"
    GOOGLE = "google"
    TIKTOK = "tiktok"
    PINTEREST = "pinterest"
    X = "x"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CampaignObjective(StrEnum):
    LEAD_GENERATION = "lead_generation"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    CONVERSIONS = "conversions"


class DecisionType(StrEnum):
    PAUSE_CAMPAIGN = "pause_campaign"
    NOTIFY_SEYMA = "notify_seyma"
    ESCALATE_HUMAN = "escalate_human"
    AUTO_REPLY = "auto_reply"
    SCORE_LEAD = "score_lead"
    ASSIGN_LEAD = "assign_lead"


class DecisionOutcome(StrEnum):
    APPLIED = "applied"
    PENDING_APPROVAL = "pending_approval"
    REVERTED = "reverted"
    FAILED = "failed"


class ObjectionCategory(StrEnum):
    PRICE = "price"
    TIMING = "timing"
    COMPETITOR = "competitor"
    TRUST = "trust"
    FEATURE = "feature"
    OTHER = "other"


class AgentHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------


class Lead(BaseModel):
    """A single lead in the CRM.

    Mirrors NocoDB ``leads`` table after V2 migration. ``Id`` is NocoDB's
    auto-increment primary key, populated only when reading from the DB.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None

    # Identity / contact
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    sector: str | None = None
    location: str | None = None  # "Bodrum / Mugla"

    # Scoring & status
    lead_score: int = Field(default=0, ge=0, le=10)
    lead_status: LeadStatus = LeadStatus.COLD
    source: LeadSource = LeadSource.MANUAL

    # KVKK / GDPR (CAIDO requirement)
    consent_status: bool = False
    consent_source: str | None = None
    consent_recorded_at: datetime | None = None

    # Timing
    first_contact_at: datetime | None = None
    first_response_time_min: int | None = None
    last_action_at: datetime | None = None

    # Pipeline economics
    cac_attributed_try: float | None = None
    expected_revenue_try: float | None = None

    # Zernio cross-reference
    zernio_thread_id: str | None = None
    zernio_account_id: str | None = None

    # Routing
    assigned_to: str | None = None  # agent name
    tags: list[str] = Field(default_factory=list)

    # Free-form notes
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.replace(" ", "").replace("-", "")

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.strip().lower() or None


# ---------------------------------------------------------------------------
# Lead Message
# ---------------------------------------------------------------------------


class LeadMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None
    lead_id: int | None = None  # NocoDB linked record FK
    direction: MessageDirection = MessageDirection.OUTBOUND
    channel: MessageChannel | None = None
    body: str = ""
    agent_name: str | None = None
    zernio_message_id: str | None = None
    is_auto_generated: bool = False
    cbo_compliant: bool = True  # default True; CBO checker can flip to False
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


class Campaign(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None
    external_campaign_id: str | None = None
    platform: CampaignPlatform
    name: str
    objective: CampaignObjective | None = None
    status: CampaignStatus = CampaignStatus.ACTIVE
    budget_daily_try: float | None = None
    started_at: datetime | None = None
    paused_at: datetime | None = None
    pause_reason: str | None = None
    total_spend_try: float = 0.0
    target_audience: str | None = None  # raw JSON string
    created_by_agent: str | None = None


# ---------------------------------------------------------------------------
# Daily Metrics
# ---------------------------------------------------------------------------


class DailyMetric(BaseModel):
    """One row per (date, channel) combination.

    Channel "total" rows are aggregates across all channels for the day.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None
    date: str  # YYYY-MM-DD
    channel: str  # CampaignPlatform value or "total"
    impressions: int = 0
    clicks: int = 0
    leads_count: int = 0
    hot_leads_count: int = 0
    conversions_count: int = 0
    spend_try: float = 0.0
    revenue_try: float = 0.0
    cac_try: float | None = None
    cpl_try: float | None = None
    ctr_pct: float | None = None
    pipeline_value_try: float = 0.0
    notes: str | None = None


# ---------------------------------------------------------------------------
# Decision Log (CAIDO audit)
# ---------------------------------------------------------------------------


class DecisionLog(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None
    timestamp: datetime
    agent_name: str
    decision_type: DecisionType
    target_entity: str  # "lead#123", "campaign#456"
    reason: str
    data_snapshot: str | None = None  # raw JSON string for audit
    human_required: bool = False
    human_acknowledged_at: datetime | None = None
    outcome: DecisionOutcome = DecisionOutcome.APPLIED


# ---------------------------------------------------------------------------
# Objection Log
# ---------------------------------------------------------------------------


class ObjectionLog(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Id: int | None = None
    lead_id: int | None = None
    objection_text: str
    objection_category: ObjectionCategory = ObjectionCategory.OTHER
    response_template_used: str | None = None
    response_text: str | None = None
    outcome: str = "pending"  # converted | still_objecting | lost | pending
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Agent Health
# ---------------------------------------------------------------------------


class AgentHealth(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_name: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    total_runs_today: int = 0
    total_leads_processed_today: int = 0
    status: AgentHealthStatus = AgentHealthStatus.HEALTHY


# ---------------------------------------------------------------------------
# Hot Lead Alert (Seyma notification payload)
# ---------------------------------------------------------------------------


class HotLeadAlert(BaseModel):
    """Payload sent to seyma_notifications when score >= 8.

    Format used by ``notify_seyma`` tool — also rendered into Şeyma's email.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    lead_id: int
    lead_name: str | None = None
    lead_company: str | None = None
    lead_score: int
    source: LeadSource
    summary: str
    suggested_next_action: str | None = None
    created_at: datetime


__all__ = [
    "Lead",
    "LeadMessage",
    "Campaign",
    "DailyMetric",
    "DecisionLog",
    "ObjectionLog",
    "AgentHealth",
    "HotLeadAlert",
    "LeadStatus",
    "LeadSource",
    "MessageDirection",
    "MessageChannel",
    "CampaignPlatform",
    "CampaignStatus",
    "CampaignObjective",
    "DecisionType",
    "DecisionOutcome",
    "ObjectionCategory",
    "AgentHealthStatus",
]
