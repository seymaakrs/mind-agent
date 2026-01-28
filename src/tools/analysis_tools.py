"""
Analysis tools for business analysis reports (SWOT, etc.).

Reports are stored in Firebase: businesses/{businessId}/reports/{reportId}
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


def _generate_report_id(report_type: str) -> str:
    """Generate a unique report ID.

    Format: {type}-{YYYYMMDD}-{random6hex}
    Example: swot-20260123-abc123
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_hex = secrets.token_hex(3)  # 6 hex chars
    return f"{report_type}-{date_str}-{random_hex}"


@function_tool(strict_mode=False)
async def save_swot_report(
    business_id: str,
    strengths: list[dict[str, str]],
    weaknesses: list[dict[str, str]],
    opportunities: list[dict[str, str]],
    threats: list[dict[str, str]],
    summary: str,
    recommendations: list[str],
    data_sources: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """
    Save a SWOT analysis report for a business.

    Args:
        business_id: Business ID.
        strengths: List of strengths, each with 'title' and 'description'.
            Example: [{"title": "Strong brand", "description": "Well-known in market"}]
        weaknesses: List of weaknesses, each with 'title' and 'description'.
        opportunities: List of opportunities, each with 'title' and 'description'.
        threats: List of threats, each with 'title' and 'description'.
        summary: Overall summary of the SWOT analysis.
        recommendations: List of 3-5 actionable recommendations.
        data_sources: Which data sources were used for analysis.
            Example: {"profile": true, "website": true, "web_search": false}

    Returns:
        dict with report_id and success status.
    """
    try:
        # Validate inputs
        for category, items in [
            ("strengths", strengths),
            ("weaknesses", weaknesses),
            ("opportunities", opportunities),
            ("threats", threats),
        ]:
            if not items or len(items) < 1:
                return {
                    "success": False,
                    "error": f"{category} must have at least 1 item with 'title' and 'description'.",
                }
            for item in items:
                if not isinstance(item, dict) or "title" not in item or "description" not in item:
                    return {
                        "success": False,
                        "error": f"Each {category} item must have 'title' and 'description' fields.",
                    }

        if not recommendations or len(recommendations) < 1:
            return {
                "success": False,
                "error": "recommendations must have at least 1 item.",
            }

        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report_id = _generate_report_id("swot")

        report_data = {
            "id": report_id,
            "type": "swot",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "agent",
            "strengths": strengths,
            "weaknesses": weaknesses,
            "opportunities": opportunities,
            "threats": threats,
            "summary": summary,
            "recommendations": recommendations,
            "data_sources": data_sources or {"profile": True, "website": False, "web_search": False},
        }

        doc_client.set_document(report_id, report_data)

        return {
            "success": True,
            "report_id": report_id,
            "message": f"SWOT analysis report saved: {report_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_reports(
    business_id: str,
    report_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Get analysis reports for a business.

    Args:
        business_id: Business ID.
        report_type: Filter by report type ("swot", etc.). None for all types.
        limit: Maximum number of reports to return.

    Returns:
        dict with reports list.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/reports")

        all_reports = doc_client.list_documents(limit=100)

        # Filter by type if specified
        if report_type:
            all_reports = [r for r in all_reports if r.get("type") == report_type]

        # Sort by created_at descending (newest first)
        all_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Apply limit
        all_reports = all_reports[:limit]

        return {
            "success": True,
            "reports": all_reports,
            "count": len(all_reports),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "reports": []}


@function_tool(strict_mode=False)
async def save_instagram_report(
    business_id: str,
    date_range: str,
    total_posts: int,
    totals: dict[str, Any],
    by_type: dict[str, Any],
    top_posts: list[dict[str, Any]],
    insights: list[str],
    recommendations: list[str],
    best_posting_time: str | None = None,
) -> dict[str, Any]:
    """
    Save an Instagram metrics analysis report for a business.

    Args:
        business_id: Business ID.
        date_range: Analysis date range (e.g., "2026-01-17 - 2026-01-24").
        total_posts: Total number of posts analyzed.
        totals: Aggregated metrics dict with keys: reach, views, interactions, shares, saved.
        by_type: Breakdown by content type. Keys: reels, image, carousel.
            Each with: count, reach, views, interactions, and optional notes.
        top_posts: List of top performing posts with: id, type, reach, views, permalink.
        insights: List of key insights from the analysis.
        recommendations: List of actionable recommendations.
        best_posting_time: Best posting time window (e.g., "19:00-21:00").

    Returns:
        dict with report_id and success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report_id = _generate_report_id("instagram")

        report_data = {
            "id": report_id,
            "type": "instagram_weekly",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "agent",
            "date_range": date_range,
            "total_posts": total_posts,
            "totals": totals,
            "by_type": by_type,
            "top_posts": top_posts,
            "insights": insights,
            "recommendations": recommendations,
            "best_posting_time": best_posting_time,
        }

        doc_client.set_document(report_id, report_data)

        return {
            "success": True,
            "report_id": report_id,
            "message": f"Instagram metrics report saved: {report_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool(strict_mode=False)
async def save_custom_report(
    business_id: str,
    title: str,
    summary: str,
    blocks: list[dict[str, Any]],
    tags: list[str] | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a custom report with flexible block-based content structure.

    Use this for any report type that doesn't fit SWOT or Instagram formats.
    Examples: AI trends, market research, competitor analysis, content audit, etc.

    Args:
        business_id: Business ID.
        title: Report title (e.g., "Son 1 Haftada AI Gelişmeleri").
        summary: Brief summary for list views (1-2 sentences).
        blocks: List of content blocks. Each block has a 'type' and type-specific fields.

            Supported block types:
            - {"type": "text", "content": "Paragraph text..."}
            - {"type": "heading", "content": "Section Title", "level": 1|2|3}
            - {"type": "list", "items": ["Item 1", "Item 2"], "ordered": false}
            - {"type": "table", "headers": ["Col1", "Col2"], "rows": [["a", "b"], ["c", "d"]]}
            - {"type": "quote", "content": "Important quote or highlight"}
            - {"type": "code", "content": "code here", "language": "python"}
            - {"type": "divider"}

        tags: Optional list of tags for filtering (e.g., ["ai", "weekly", "tech"]).
        sources: Optional list of source URLs used for the report.

    Returns:
        dict with report_id and success status.
    """
    try:
        # Validate blocks
        if not blocks or len(blocks) < 1:
            return {
                "success": False,
                "error": "blocks must have at least 1 item.",
            }

        valid_types = {"text", "heading", "list", "table", "quote", "code", "divider"}
        for i, block in enumerate(blocks):
            if not isinstance(block, dict) or "type" not in block:
                return {
                    "success": False,
                    "error": f"Block {i} must be a dict with 'type' field.",
                }
            if block["type"] not in valid_types:
                return {
                    "success": False,
                    "error": f"Block {i} has invalid type '{block['type']}'. Valid types: {valid_types}",
                }
            # Type-specific validation
            block_type = block["type"]
            if block_type == "text" and "content" not in block:
                return {"success": False, "error": f"Block {i} (text) requires 'content' field."}
            if block_type == "heading" and ("content" not in block or "level" not in block):
                return {"success": False, "error": f"Block {i} (heading) requires 'content' and 'level' fields."}
            if block_type == "list" and "items" not in block:
                return {"success": False, "error": f"Block {i} (list) requires 'items' field."}
            if block_type == "table" and ("headers" not in block or "rows" not in block):
                return {"success": False, "error": f"Block {i} (table) requires 'headers' and 'rows' fields."}
            if block_type == "quote" and "content" not in block:
                return {"success": False, "error": f"Block {i} (quote) requires 'content' field."}
            if block_type == "code" and "content" not in block:
                return {"success": False, "error": f"Block {i} (code) requires 'content' field."}

        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report_id = _generate_report_id("report")

        report_data = {
            "id": report_id,
            "type": "custom",
            "title": title,
            "summary": summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "agent",
            "blocks": blocks,
        }

        if tags:
            report_data["tags"] = tags
        if sources:
            report_data["sources"] = sources

        doc_client.set_document(report_id, report_data)

        return {
            "success": True,
            "report_id": report_id,
            "message": f"Custom report saved: {report_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_report(
    business_id: str,
    report_id: str,
) -> dict[str, Any]:
    """
    Get a specific analysis report by ID.

    Args:
        business_id: Business ID.
        report_id: Report ID (e.g., "swot-20260123-abc123").

    Returns:
        dict with report details.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report = doc_client.get_document(report_id)

        if report:
            return {
                "success": True,
                "found": True,
                "report": report,
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": f"Report not found: {report_id}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_analysis_tools() -> list:
    """Return list of analysis tools for the agent (SWOT only)."""
    return [
        save_swot_report,
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
    "save_swot_report",
    "save_custom_report",
    "save_instagram_report",
    "get_reports",
    "get_report",
    "get_analysis_tools",
    "get_report_tools",
]
