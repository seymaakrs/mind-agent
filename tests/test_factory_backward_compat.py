"""H-6 — Factory backward-compat contract for Faz 2 unit tools.

PR #27 splits the Director's tool surface into three unit factories
(``get_outreach_unit_tools`` / ``get_cx_unit_tools`` /
``get_quality_unit_tools``) plus a lead-level set
(``get_lead_management_tools``). The legacy ``get_management_tools()``
union MUST remain the superset so older agent wiring keeps working
without changes.

Regression here breaks ``sales_manager_agent.py`` and any other caller
that imports the legacy name — typically silent at unit level until
runtime when an agent looks for a missing tool.
"""
from __future__ import annotations

import pytest

pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")

from src.tools.sales import management_tools as mt


def _names(tools):
    """Tools may be FunctionTool instances; introspect a stable name."""
    out = []
    for t in tools:
        n = getattr(t, "name", None) or getattr(t, "__name__", None) or str(t)
        out.append(n)
    return out


def test_unit_factories_return_non_empty_lists():
    assert len(mt.get_outreach_unit_tools()) >= 1
    assert len(mt.get_cx_unit_tools()) >= 1
    assert len(mt.get_quality_unit_tools()) >= 1
    assert len(mt.get_lead_management_tools()) >= 1


def test_management_tools_is_union_of_units():
    """Legacy ``get_management_tools`` must equal the union of all unit factories."""
    union = (
        mt.get_outreach_unit_tools()
        + mt.get_cx_unit_tools()
        + mt.get_quality_unit_tools()
        + mt.get_lead_management_tools()
    )
    mgmt = mt.get_management_tools()
    assert _names(mgmt) == _names(union), (
        "get_management_tools must remain the union of all unit factories. "
        f"union={_names(union)}\nmgmt={_names(mgmt)}"
    )


def test_outreach_unit_contains_expected_tools():
    names = _names(mt.get_outreach_unit_tools())
    # These are the Avcilik birimi public names; renames require a paired
    # update in the Sales Director instructions.
    assert "outreach_pause" in names
    assert "outreach_resume" in names
    assert "outreach_set_daily_limit" in names


def test_cx_unit_contains_expected_tools():
    names = _names(mt.get_cx_unit_tools())
    assert "auto_reply_pause" in names
    assert "auto_reply_resume" in names
    assert "auto_reply_template_update" in names
    assert "flag_for_human" in names


def test_quality_unit_contains_expected_tools():
    names = _names(mt.get_quality_unit_tools())
    assert "guardian_set_thresholds" in names
    assert "compliance_audit" in names


def test_no_duplicates_across_units():
    """A tool MUST live in exactly one unit; the union has no duplicates."""
    seen: dict[str, str] = {}
    for unit_name, getter in (
        ("outreach", mt.get_outreach_unit_tools),
        ("cx", mt.get_cx_unit_tools),
        ("quality", mt.get_quality_unit_tools),
        ("lead", mt.get_lead_management_tools),
    ):
        for tool in getter():
            n = getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if n in seen:
                pytest.fail(f"Tool {n!r} in both {seen[n]!r} and {unit_name!r}")
            seen[n] = unit_name
