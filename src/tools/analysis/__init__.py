"""Analysis tools package — SEO analysis and business reports."""

from .reports import (
    save_swot_report,
    get_reports,
    get_report,
    save_instagram_report,
    save_custom_report,
)
from .seo import (
    save_seo_report,
    save_seo_keywords,
    get_seo_keywords,
    save_seo_summary,
)


def get_analysis_tools() -> list:
    """Return list of analysis tools for the agent (SWOT + SEO + Custom)."""
    return [
        save_swot_report,
        save_seo_report,
        save_seo_keywords,
        save_seo_summary,
        get_seo_keywords,
        save_custom_report,
        get_reports,
        get_report,
    ]


def get_report_tools() -> list:
    """Return report saving tools (for marketing agent to save Instagram reports)."""
    return [
        save_instagram_report,
        get_reports,
        get_report,
    ]


__all__ = [
    "save_swot_report", "save_seo_report", "save_seo_keywords", "save_seo_summary",
    "get_seo_keywords", "save_custom_report", "save_instagram_report",
    "get_reports", "get_report",
    "get_analysis_tools", "get_report_tools",
]
