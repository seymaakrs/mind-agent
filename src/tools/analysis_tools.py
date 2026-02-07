"""
Analysis tools for business analysis reports (SWOT, SEO, etc.).

Reports are stored in Firebase: businesses/{businessId}/reports/{reportId}
"""
from __future__ import annotations

import re
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


def _flatten_block_for_firestore(block: dict[str, Any]) -> dict[str, Any]:
    """Flatten a block to avoid Firestore nested entity errors.

    Firestore has limits on nested arrays/maps. This function converts
    deeply nested structures to JSON strings.
    """
    flattened = {"type": block.get("type", "text")}

    for key, value in block.items():
        if key == "type":
            continue
        # Convert nested arrays (like table rows) to JSON strings
        if key == "rows" and isinstance(value, list):
            import json
            flattened["rows_json"] = json.dumps(value, ensure_ascii=False)
        elif key == "items" and isinstance(value, list) and any(isinstance(item, (list, dict)) for item in value):
            import json
            flattened["items_json"] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[key] = value

    return flattened


@function_tool(strict_mode=False)
async def save_custom_report(
    business_id: str,
    title: str,
    summary: str,
    blocks: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """
    Save a custom report with flexible block-based content structure.

    Use this for any report type that doesn't fit SWOT or Instagram formats.
    Examples: AI trends, market research, competitor analysis, content audit, etc.

    IMPORTANT: The 'blocks' parameter is REQUIRED. You MUST provide at least one block.

    Args:
        business_id: Business ID (REQUIRED).
        title: Report title (REQUIRED, e.g., "Son 1 Haftada AI Gelişmeleri").
        summary: Brief summary for list views (REQUIRED, 1-2 sentences).
        blocks: REQUIRED - List of content blocks. You MUST provide this parameter!
            Each block must have a 'type' field.

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
        # Validate blocks - THIS IS REQUIRED
        if blocks is None or not isinstance(blocks, list) or len(blocks) < 1:
            return {
                "success": False,
                "error": "REQUIRED PARAMETER MISSING: 'blocks' must be a list with at least 1 item. "
                         "Example: blocks=[{\"type\": \"text\", \"content\": \"Your text here\"}]",
            }

        valid_types = {"text", "heading", "list", "table", "quote", "code", "divider"}
        flattened_blocks = []

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

            # Flatten block to avoid Firestore nested entity errors
            flattened_blocks.append(_flatten_block_for_firestore(block))

        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report_id = _generate_report_id("report")

        report_data = {
            "id": report_id,
            "type": "custom",
            "title": title,
            "summary": summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "agent",
            "blocks": flattened_blocks,
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


@function_tool(strict_mode=False)
async def save_seo_report(
    business_id: str,
    business_website_analysis: dict[str, Any],
    competitors: list[dict[str, Any]],
    keyword_recommendations: list[dict[str, Any]],
    technical_issues: list[dict[str, Any]],
    content_recommendations: list[str],
    summary: str,
    overall_score: int,
    competitor_urls: list[str] | None = None,
    data_sources: dict[str, bool] | None = None,
    score_breakdown: dict[str, Any] | None = None,
    technical_seo: dict[str, Any] | None = None,
    mobile_analysis: dict[str, Any] | None = None,
    content_quality: dict[str, Any] | None = None,
    serp_positions: list[dict[str, Any]] | None = None,
    serp_visibility_score: int | None = None,
) -> dict[str, Any]:
    """
    Save a comprehensive SEO analysis report for a business.

    Args:
        business_id: Business ID.
        business_website_analysis: SEO analysis of the business's own website.
            Should include: url, meta_tags, headings, images, links, schema_markup,
            url_analysis, seo_score, word_count, keyword_density.
        competitors: List of competitor SEO analyses.
            Each with: domain, pages_analyzed, common_keywords, avg_content_length,
            schema_types_used, top_headings, seo_score.
        keyword_recommendations: List of recommended keywords.
            Each with: keyword, category (primary/secondary/long_tail/local),
            search_intent (informational/transactional/navigational),
            priority (high/medium/low), competitor_usage, notes.
        technical_issues: List of SEO issues found.
            Each with: type (error/warning/info), issue, recommendation.
        content_recommendations: List of content improvement suggestions.
        summary: Executive summary of the SEO analysis (2-3 paragraphs).
        overall_score: Overall SEO score (0-100).
        competitor_urls: List of competitor URLs that were analyzed.
        data_sources: Which data sources were used.
            Example: {"business_website": true, "competitors": true, "web_search": true}
        score_breakdown: v2 scoring breakdown with 6-category detail (optional).
        technical_seo: Technical SEO check results - robots.txt, sitemap, SSL, TTFB (optional).
        mobile_analysis: Mobile-friendliness check results (optional).
        content_quality: Content quality analysis - depth, readability, keyword placement (optional).
        serp_positions: Per-keyword SERP position data from check_serp_position (optional).
        serp_visibility_score: Overall SERP visibility score 0-100 (optional).

    Returns:
        dict with report_id and success status.
    """
    try:
        # Validate inputs
        if not business_website_analysis:
            return {
                "success": False,
                "error": "business_website_analysis is required",
            }

        if not keyword_recommendations or len(keyword_recommendations) < 1:
            return {
                "success": False,
                "error": "keyword_recommendations must have at least 1 item",
            }

        for i, kw in enumerate(keyword_recommendations):
            if not isinstance(kw, dict) or "keyword" not in kw:
                return {
                    "success": False,
                    "error": f"keyword_recommendations[{i}] must have 'keyword' field",
                }

        if not technical_issues:
            technical_issues = []

        if not content_recommendations:
            content_recommendations = []

        if overall_score < 0 or overall_score > 100:
            return {
                "success": False,
                "error": "overall_score must be between 0 and 100",
            }

        doc_client = get_document_client(f"businesses/{business_id}/reports")

        report_id = _generate_report_id("seo")

        report_data: dict[str, Any] = {
            "id": report_id,
            "type": "seo",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "agent",
            "overall_score": overall_score,
            "summary": summary,
            "business_website_analysis": business_website_analysis,
            "competitors": competitors or [],
            "competitor_urls": competitor_urls or [],
            "keyword_recommendations": keyword_recommendations,
            "technical_issues": technical_issues,
            "content_recommendations": content_recommendations,
            "data_sources": data_sources or {
                "business_website": True,
                "competitors": bool(competitors),
                "web_search": True,
            },
        }

        # v2 optional fields — only include when provided
        if score_breakdown is not None:
            report_data["score_breakdown"] = score_breakdown
        if technical_seo is not None:
            report_data["technical_seo"] = technical_seo
        if mobile_analysis is not None:
            report_data["mobile_analysis"] = mobile_analysis
        if content_quality is not None:
            report_data["content_quality"] = content_quality
        if serp_positions is not None:
            report_data["serp_positions"] = serp_positions
        if serp_visibility_score is not None:
            report_data["serp_visibility_score"] = serp_visibility_score

        doc_client.set_document(report_id, report_data)

        return {
            "success": True,
            "report_id": report_id,
            "message": f"SEO analysis report saved: {report_id}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool(strict_mode=False)
async def save_seo_keywords(
    business_id: str,
    keywords: list[dict[str, Any]] | None = None,
    source: str = "seo_analysis",
    report_id: str | None = None,
) -> dict[str, Any]:
    """
    Save recommended SEO keywords for a business.

    Keywords are saved as a single document: businesses/{business_id}/seo/keywords
    All keywords stored as an array in the 'items' field.
    This document is OVERWRITTEN on each new SEO analysis (single version, always current).

    IMPORTANT: The 'keywords' parameter is REQUIRED. You MUST provide at least one keyword.

    Args:
        business_id: Business ID (REQUIRED).
        keywords: REQUIRED - List of keyword objects. You MUST provide this parameter!
            Each keyword object should have:
            - keyword: The keyword string (REQUIRED)
            - category: primary, secondary, long_tail, local (default: secondary)
            - search_intent: informational, transactional, navigational (default: informational)
            - priority: high, medium, low (default: medium)
            - competitor_usage: Number of competitors using this keyword (default: 0)
            - notes: Optional notes about the keyword

            Example: keywords=[{"keyword": "istanbul pastane", "category": "local", "priority": "high"}]

        source: Source of keywords (default: "seo_analysis").
        report_id: Associated SEO report ID (optional).

    Returns:
        dict with success status and saved keyword count.
    """
    try:
        if keywords is None or not isinstance(keywords, list) or len(keywords) < 1:
            return {
                "success": False,
                "error": "REQUIRED PARAMETER MISSING: 'keywords' must be a list with at least 1 item. "
                         "Example: keywords=[{\"keyword\": \"istanbul pastane\", \"category\": \"local\"}]",
            }

        # Use seo collection, keywords as a single document
        doc_client = get_document_client(f"businesses/{business_id}/seo")

        timestamp = datetime.now(timezone.utc).isoformat()

        # Build normalized keyword items
        keyword_items = []
        for kw in keywords:
            if not isinstance(kw, dict) or "keyword" not in kw:
                continue

            keyword_items.append({
                "keyword": kw["keyword"],
                "category": kw.get("category", "secondary"),
                "search_intent": kw.get("search_intent", "informational"),
                "priority": kw.get("priority", "medium"),
                "competitor_usage": kw.get("competitor_usage", 0),
                "notes": kw.get("notes", ""),
            })

        # Sort by priority (high > medium > low), then by competitor_usage
        priority_order = {"high": 0, "medium": 1, "low": 2}
        keyword_items.sort(
            key=lambda x: (
                priority_order.get(x.get("priority", "medium"), 1),
                -x.get("competitor_usage", 0),
            )
        )

        # Single document with all keywords as array
        keywords_doc = {
            "items": keyword_items,
            "total_count": len(keyword_items),
            "source": source,
            "updated_at": timestamp,
        }

        if report_id:
            keywords_doc["report_id"] = report_id

        # Overwrite the keywords document (not merge - always fresh)
        doc_client.set_document("keywords", keywords_doc, merge=False)

        return {
            "success": True,
            "saved_count": len(keyword_items),
            "message": f"Saved {len(keyword_items)} SEO keywords to seo/keywords",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_seo_keywords(
    business_id: str,
    category: str | None = None,
    priority: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Get saved SEO keywords for a business.

    Keywords are stored as a single document: businesses/{business_id}/seo/keywords

    Args:
        business_id: Business ID.
        category: Filter by category (primary, secondary, long_tail, local). None for all.
        priority: Filter by priority (high, medium, low). None for all.
        limit: Maximum keywords to return (default 50).

    Returns:
        dict with keywords list grouped by category.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/seo")

        # Get the keywords document
        keywords_doc = doc_client.get_document("keywords")

        if not keywords_doc:
            return {
                "success": True,
                "keywords": [],
                "by_category": {"primary": [], "secondary": [], "long_tail": [], "local": []},
                "count": 0,
                "message": "No SEO keywords found for this business",
            }

        all_keywords = keywords_doc.get("items", [])

        # Apply filters
        if category:
            all_keywords = [k for k in all_keywords if k.get("category") == category]
        if priority:
            all_keywords = [k for k in all_keywords if k.get("priority") == priority]

        # Apply limit
        all_keywords = all_keywords[:limit]

        # Group by category
        by_category = {
            "primary": [],
            "secondary": [],
            "long_tail": [],
            "local": [],
        }
        for kw in all_keywords:
            cat = kw.get("category", "secondary")
            if cat in by_category:
                by_category[cat].append(kw)

        return {
            "success": True,
            "keywords": all_keywords,
            "by_category": by_category,
            "count": len(all_keywords),
            "total_in_db": keywords_doc.get("total_count", 0),
            "updated_at": keywords_doc.get("updated_at"),
            "report_id": keywords_doc.get("report_id"),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "keywords": []}


@function_tool(strict_mode=False)
async def save_seo_summary(
    business_id: str,
    overall_score: int,
    top_keywords: list[str],
    main_issues: list[str],
    competitor_count: int,
    competitor_avg_score: int,
    business_seo_score: int | None = None,
    last_report_id: str | None = None,
    serp_visibility_score: int | None = None,
    score_breakdown: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Save SEO summary to both seo/summary document and agent memory.

    This document is OVERWRITTEN on each new SEO analysis (single version, always current).
    Provides quick access to SEO status without fetching full reports.
    MUST be called after save_seo_report and save_seo_keywords!

    Args:
        business_id: Business ID (REQUIRED).
        overall_score: Overall SEO score (0-100).
        top_keywords: Top 5-10 recommended keywords.
        main_issues: Top 3-5 technical issues to fix.
        competitor_count: Number of competitors analyzed.
        competitor_avg_score: Average SEO score of competitors.
        business_seo_score: Business website's own SEO score (optional, defaults to overall_score).
        last_report_id: ID of the latest SEO report (in reports/ collection).
        serp_visibility_score: Real search visibility score 0-100 from check_serp_position (optional).
        score_breakdown: v2 scoring breakdown summary with category scores (optional).

    Returns:
        dict with success status.
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Save to seo/summary document (OVERWRITE, not merge)
        seo_doc_client = get_document_client(f"businesses/{business_id}/seo")

        summary_data: dict[str, Any] = {
            "overall_score": overall_score,
            "business_seo_score": business_seo_score or overall_score,
            "top_keywords": top_keywords[:10],  # Limit to 10
            "main_issues": main_issues[:5],  # Limit to 5
            "competitor_count": competitor_count,
            "competitor_avg_score": competitor_avg_score,
            "last_report_id": last_report_id,  # Reference to reports/{report_id}
            "last_analysis_date": timestamp,
            "updated_at": timestamp,
        }

        # v2 optional fields
        if serp_visibility_score is not None:
            summary_data["serp_visibility_score"] = serp_visibility_score
        if score_breakdown is not None:
            summary_data["score_breakdown"] = score_breakdown

        # Overwrite the summary document (not merge - always fresh)
        seo_doc_client.set_document("summary", summary_data, merge=False)

        # 2. Update agent memory with SEO info
        memory_client = get_document_client(f"businesses/{business_id}/agent_memory")

        # Get existing memory
        existing_memory = memory_client.get_document("marketing") or {}

        # Add/update SEO section
        seo_memory: dict[str, Any] = {
            "seo_score": overall_score,
            "seo_vs_competitors": f"{overall_score} vs rakip ort. {competitor_avg_score}",
            "top_seo_keywords": ", ".join(top_keywords[:5]),
            "seo_issues": "; ".join(main_issues[:3]) if main_issues else "Yok",
            "last_seo_analysis": timestamp[:10],  # Just date
        }

        # Add SERP visibility to agent memory if available
        if serp_visibility_score is not None:
            seo_memory["serp_visibility"] = serp_visibility_score

        # Merge with existing memory (keep other memory fields)
        updated_memory = {**existing_memory, **seo_memory}
        memory_client.set_document("marketing", updated_memory, merge=True)

        return {
            "success": True,
            "message": "SEO summary saved to seo/summary and agent_memory",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    "save_swot_report",
    "save_seo_report",
    "save_seo_keywords",
    "save_seo_summary",
    "get_seo_keywords",
    "save_custom_report",
    "save_instagram_report",
    "get_reports",
    "get_report",
    "get_analysis_tools",
    "get_report_tools",
]
