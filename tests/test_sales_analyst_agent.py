"""Wiring tests for the Sales Analyst agent.

Confirms:
- The agent factory builds with the expected name + tool list.
- All 7 reporting tools are present and read-only (no write tool leaks in).
- Instructions reference the read-only contract.
"""
from __future__ import annotations

from src.agents.sales.sales_analyst_agent import create_sales_analyst_agent
from src.agents.instructions.sales import SALES_ANALYST_INSTRUCTIONS


EXPECTED_TOOL_NAMES = {
    "count_leads",
    "list_leads",
    "lead_funnel",
    "channel_breakdown",
    "stale_leads",
    "lead_timeline",
    "daily_digest",
}

# Write tool names that MUST NEVER appear on the analyst agent.
FORBIDDEN_TOOL_NAMES = {
    "upsert_lead",
    "update_lead",
    "create_lead",
    "log_lead_message",
    "notify_seyma",
}


def _tool_name(tool):
    return getattr(tool, "name", None) or getattr(tool, "name_override", None)


def test_agent_name_is_sales_analyst():
    agent = create_sales_analyst_agent()
    assert agent.name == "sales_analyst"


def test_all_seven_reporting_tools_present():
    agent = create_sales_analyst_agent()
    names = {_tool_name(t) for t in agent.tools}
    missing = EXPECTED_TOOL_NAMES - names
    assert not missing, f"Missing expected reporting tools: {missing}"


def test_no_write_tools_leaked_in():
    agent = create_sales_analyst_agent()
    names = {_tool_name(t) for t in agent.tools}
    leaked = FORBIDDEN_TOOL_NAMES & names
    assert not leaked, (
        f"Sales Analyst is read-only; write tools leaked in: {leaked}"
    )


def test_instructions_emphasize_readonly():
    text = SALES_ANALYST_INSTRUCTIONS.lower()
    assert "read-only" in text or "yazma yapma" in text


def test_instructions_mention_today_date_marker():
    assert "[TODAY:" in SALES_ANALYST_INSTRUCTIONS
