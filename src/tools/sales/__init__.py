"""Sales (Customer Agent) tool exports."""
from __future__ import annotations

from src.tools.sales.nocodb_tools import (
    create_lead,
    get_lead,
    log_lead_message,
    notify_seyma,
    query_leads,
    update_lead,
)
from src.tools.sales.sales_query_tools import (
    get_agent_health_summary,
    get_cac_by_channel,
    get_hot_leads,
    get_hot_leads_count,
    get_pipeline_value,
    get_recent_decisions,
    get_today_funnel,
    get_total_leads_count,
)


def get_sales_crud_tools() -> list:
    """Tools for write-capable sales agents (clay, ig_dm, linkedin, meta)."""
    return [
        create_lead,
        update_lead,
        get_lead,
        query_leads,
        log_lead_message,
        notify_seyma,
    ]


def get_sales_query_tools() -> list:
    """Read-only tools for sales_query_agent (Şeyma's chat assistant).

    No mutations — query agent CANNOT write to the CRM.
    """
    return [
        get_hot_leads_count,
        get_hot_leads,
        get_total_leads_count,
        get_pipeline_value,
        get_today_funnel,
        get_cac_by_channel,
        get_recent_decisions,
        get_agent_health_summary,
        # Read-only access to a single lead is also useful in the chat:
        get_lead,
        query_leads,
    ]


__all__ = [
    "get_sales_crud_tools",
    "get_sales_query_tools",
    "create_lead",
    "update_lead",
    "get_lead",
    "query_leads",
    "log_lead_message",
    "notify_seyma",
    "get_hot_leads_count",
    "get_hot_leads",
    "get_total_leads_count",
    "get_pipeline_value",
    "get_today_funnel",
    "get_cac_by_channel",
    "get_recent_decisions",
    "get_agent_health_summary",
]
