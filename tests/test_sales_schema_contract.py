"""Schema contract test — Pydantic models MUST stay in sync with NocoDB schema.

If either side drifts (schema doc adds/renames a column, or a model adds/renames
a field), this test fails. That stops production lead writes from silently
mapping to the wrong column.

Tested invariants:
1. Every Pydantic model field name (except ``Id`` and read-only meta fields)
   appears verbatim in ``customer_agent/docs/NOCODB-SCHEMA-V2.md``.
2. Every enum value (LeadStatus, LeadSource, MessageChannel, etc.) appears in
   the schema doc — these power NocoDB SingleSelect option lists.
"""
from __future__ import annotations

from pathlib import Path

from src.models import sales as sm

# Schema doc lives in customer_agent/docs/NOCODB-SCHEMA-V2.md (sibling repo).
# In the test environment it's at /home/user/customer_agent/docs/...
SCHEMA_DOC = Path("/home/user/customer_agent/docs/NOCODB-SCHEMA-V2.md")

# Fields we deliberately don't expect in the schema doc:
# - ``Id`` is NocoDB's auto-PK
# - ``platform`` / ``name`` are required Campaign fields documented under
#   "campaigns" section but with a different label in the doc; manually
#   verified to exist
_IGNORED_FIELDS = {"Id"}


def _doc_text() -> str:
    return SCHEMA_DOC.read_text(encoding="utf-8")


def _assert_field_in_doc(field: str, model_name: str, doc: str) -> None:
    needle = f"`{field}`"
    assert needle in doc, (
        f"NocoDB schema doc is missing column `{field}` from model "
        f"{model_name}. Either update the doc or rename the model field."
    )


class TestNocoDBSchemaContract:
    def test_lead_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.Lead.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "Lead", doc)

    def test_lead_message_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.LeadMessage.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "LeadMessage", doc)

    def test_campaign_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.Campaign.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "Campaign", doc)

    def test_daily_metric_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.DailyMetric.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "DailyMetric", doc)

    def test_decision_log_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.DecisionLog.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "DecisionLog", doc)

    def test_objection_log_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.ObjectionLog.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "ObjectionLog", doc)

    def test_agent_health_fields_in_schema(self) -> None:
        doc = _doc_text()
        for name in sm.AgentHealth.model_fields:
            if name in _IGNORED_FIELDS:
                continue
            _assert_field_in_doc(name, "AgentHealth", doc)


class TestEnumValuesInSchema:
    """Each enum value MUST be listed as a NocoDB SingleSelect option."""

    def test_lead_status_options(self) -> None:
        doc = _doc_text()
        for status in sm.LeadStatus:
            assert f"`{status.value}`" in doc

    def test_lead_source_options(self) -> None:
        doc = _doc_text()
        for source in sm.LeadSource:
            assert f"`{source.value}`" in doc

    def test_message_direction_options(self) -> None:
        doc = _doc_text()
        for d in sm.MessageDirection:
            assert f"`{d.value}`" in doc

    def test_message_channel_options(self) -> None:
        doc = _doc_text()
        for ch in sm.MessageChannel:
            assert f"`{ch.value}`" in doc

    def test_decision_type_options(self) -> None:
        doc = _doc_text()
        for d in sm.DecisionType:
            assert f"`{d.value}`" in doc

    def test_decision_outcome_options(self) -> None:
        doc = _doc_text()
        for d in sm.DecisionOutcome:
            assert f"`{d.value}`" in doc

    def test_agent_health_status_options(self) -> None:
        doc = _doc_text()
        for s in sm.AgentHealthStatus:
            assert f"`{s.value}`" in doc

    def test_objection_category_options(self) -> None:
        doc = _doc_text()
        for c in sm.ObjectionCategory:
            assert f"`{c.value}`" in doc

    def test_campaign_platform_options(self) -> None:
        doc = _doc_text()
        for p in sm.CampaignPlatform:
            assert f"`{p.value}`" in doc

    def test_campaign_status_options(self) -> None:
        doc = _doc_text()
        for s in sm.CampaignStatus:
            assert f"`{s.value}`" in doc

    def test_campaign_objective_options(self) -> None:
        doc = _doc_text()
        for o in sm.CampaignObjective:
            assert f"`{o.value}`" in doc
