"""H-2 — Manager actions input validation contract.

The six Director-level write tools (``_outreach_pause_impl``, ``_resume``,
``_lead_reassign``, ``_lead_priority_set``, ``_auto_reply_template_update``,
``_outreach_daily_limit_set``) all enforce:

1. **reason** must be at least 5 characters (audit-trail hygiene)
2. **mandatory arguments** are rejected when empty/missing
3. Environment-bound table IDs are checked before any NocoDB write

If any of these guardrails regresses, the LLM can silently mutate
production state with an empty reason or against an unconfigured backend.
These tests fence the guardrails at the unit boundary so a CI failure
surfaces before a deploy.

The tests intentionally do NOT mock NocoDB — they exercise the
validation branches that return early, so no network calls are made.
"""
from __future__ import annotations

import pytest

pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")

from src.tools.sales import manager_actions as ma


# Every action requires a reason >= 5 chars. Parametrise the boundary.
SHORT_REASONS = ["", "a", "abcd", "1234"]
VALID_LONG_REASON = "audit-trail-rationale"


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", SHORT_REASONS)
async def test_outreach_resume_rejects_short_reason(reason, monkeypatch):
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "tbl_x")
    r = await ma._outreach_resume_impl(reason=reason)
    assert r["success"] is False
    assert "5 karakter" in r["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", SHORT_REASONS)
async def test_lead_reassign_rejects_short_reason(reason, monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "tbl_x")
    r = await ma._lead_reassign_impl(lead_id=42, new_owner="Seyma", reason=reason)
    assert r["success"] is False
    assert "5 karakter" in r["error"]


@pytest.mark.asyncio
async def test_lead_reassign_rejects_empty_new_owner(monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "tbl_x")
    r = await ma._lead_reassign_impl(lead_id=42, new_owner="", reason=VALID_LONG_REASON)
    assert r["success"] is False
    assert "new_owner" in r["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", SHORT_REASONS)
async def test_lead_priority_set_rejects_short_reason(reason, monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "tbl_x")
    r = await ma._lead_priority_set_impl(lead_id=42, priority="high", reason=reason)
    assert r["success"] is False
    assert "5 karakter" in r["error"]


@pytest.mark.asyncio
async def test_outreach_pause_requires_settings_table_env(monkeypatch):
    monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
    r = await ma._outreach_pause_impl(reason=VALID_LONG_REASON)
    assert r["success"] is False
    assert "NOCODB_SETTINGS_TABLE_ID" in r["error"]


@pytest.mark.asyncio
async def test_outreach_resume_requires_settings_table_env(monkeypatch):
    monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
    r = await ma._outreach_resume_impl(reason=VALID_LONG_REASON)
    assert r["success"] is False
    assert "NOCODB_SETTINGS_TABLE_ID" in r["error"]


@pytest.mark.asyncio
async def test_lead_reassign_requires_leads_table_env(monkeypatch):
    monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
    r = await ma._lead_reassign_impl(lead_id=42, new_owner="Seyma", reason=VALID_LONG_REASON)
    assert r["success"] is False
    assert "NOCODB_LEADS_TABLE_ID" in r["error"]


@pytest.mark.asyncio
async def test_outreach_daily_limit_requires_settings_table_env(monkeypatch):
    monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
    r = await ma._outreach_daily_limit_set_impl(new_limit=100, reason=VALID_LONG_REASON)
    assert r["success"] is False
    assert "NOCODB_SETTINGS_TABLE_ID" in r["error"]
