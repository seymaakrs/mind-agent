from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client
from .utils import generate_report_id


@function_tool(strict_mode=False)
async def save_seo_report(
    business_id: str,
    summary: str,
    overall_score: int,
    business_website_analysis: dict[str, Any] | None = None,
    competitors: list[dict[str, Any]] | None = None,
    keyword_recommendations: list[dict[str, Any]] | None = None,
    technical_issues: list[dict[str, Any]] | None = None,
    content_recommendations: list[str] | None = None,
    competitor_urls: list[str] | None = None,
    data_sources: dict[str, bool] | None = None,
    score_breakdown: dict[str, Any] | None = None,
    technical_seo: dict[str, Any] | None = None,
    mobile_analysis: dict[str, Any] | None = None,
    content_quality: dict[str, Any] | None = None,
    serp_positions: list[dict[str, Any]] | None = None,
    serp_visibility_score: int | None = None,
    geo_readiness_score: int | None = None,
    geo_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Save a comprehensive SEO analysis report for a business.

    Args:
        business_id: Business ID.
        summary: Executive summary of the SEO analysis (2-3 paragraphs).
        overall_score: Overall SEO score (0-100).
        business_website_analysis: SEO analysis of the business's own website.
        competitors: List of competitor SEO analyses.
        keyword_recommendations: List of recommended keywords.
        technical_issues: List of SEO issues found.
        content_recommendations: List of content improvement suggestions.
        competitor_urls: List of competitor URLs that were analyzed.
        data_sources: Which data sources were used.
        score_breakdown: v2 scoring breakdown with 6-category detail (optional).
        technical_seo: Technical SEO check results (optional).
        mobile_analysis: Mobile-friendliness check results (optional).
        content_quality: Content quality analysis (optional).
        serp_positions: Per-keyword SERP position data (optional).
        serp_visibility_score: Overall SERP visibility score 0-100 (optional).
        geo_readiness_score: GEO readiness score 0-100 (optional).
        geo_analysis: Full GEO analysis with 4-category breakdown (optional).

    Returns:
        dict with report_id and success status.
    """
    try:
        if not business_website_analysis:
            business_website_analysis = {}
        if not keyword_recommendations:
            keyword_recommendations = []
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

        report_id = generate_report_id("seo")

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

        # v2 optional fields
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
        if geo_readiness_score is not None:
            report_data["geo_readiness_score"] = geo_readiness_score
        if geo_analysis is not None:
            report_data["geo_analysis"] = geo_analysis

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
    This document is OVERWRITTEN on each new SEO analysis.

    IMPORTANT: The 'keywords' parameter is REQUIRED.

    Args:
        business_id: Business ID (REQUIRED).
        keywords: REQUIRED - List of keyword objects with 'keyword' field.
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

        doc_client = get_document_client(f"businesses/{business_id}/seo")

        timestamp = datetime.now(timezone.utc).isoformat()

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

        priority_order = {"high": 0, "medium": 1, "low": 2}
        keyword_items.sort(
            key=lambda x: (
                priority_order.get(x.get("priority", "medium"), 1),
                -x.get("competitor_usage", 0),
            )
        )

        keywords_doc = {
            "items": keyword_items,
            "total_count": len(keyword_items),
            "source": source,
            "updated_at": timestamp,
        }

        if report_id:
            keywords_doc["report_id"] = report_id

        doc_client.set_document("keywords", keywords_doc, merge=False)

        # Save top keywords to business profile
        top_kw_for_profile = [
            kw["keyword"] for kw in keyword_items
            if kw.get("priority") in ("high", "medium")
        ][:7]
        if top_kw_for_profile:
            business_client = get_document_client("businesses")
            business_client.set_document(
                business_id,
                {"profile": {"seo_keywords": top_kw_for_profile}},
                merge=True,
            )

        return {
            "success": True,
            "saved_count": len(keyword_items),
            "message": f"Saved {len(keyword_items)} SEO keywords to seo/keywords and business profile",
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

    Args:
        business_id: Business ID.
        category: Filter by category (primary, secondary, long_tail, local).
        priority: Filter by priority (high, medium, low).
        limit: Maximum keywords to return (default 50).

    Returns:
        dict with keywords list grouped by category.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/seo")

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

        if category:
            all_keywords = [k for k in all_keywords if k.get("category") == category]
        if priority:
            all_keywords = [k for k in all_keywords if k.get("priority") == priority]

        all_keywords = all_keywords[:limit]

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
    geo_readiness_score: int | None = None,
    geo_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Save SEO summary to both seo/summary document and agent memory.

    This document is OVERWRITTEN on each new SEO analysis.
    MUST be called after save_seo_report and save_seo_keywords!

    Args:
        business_id: Business ID (REQUIRED).
        overall_score: Overall SEO score (0-100).
        top_keywords: Top 5-10 recommended keywords.
        main_issues: Top 3-5 technical issues to fix.
        competitor_count: Number of competitors analyzed.
        competitor_avg_score: Average SEO score of competitors.
        business_seo_score: Business website's own SEO score (optional).
        last_report_id: ID of the latest SEO report (optional).
        serp_visibility_score: Real search visibility score 0-100 (optional).
        score_breakdown: v2 scoring breakdown summary (optional).
        geo_readiness_score: GEO readiness score 0-100 (optional).
        geo_analysis: GEO analysis summary (optional).

    Returns:
        dict with success status.
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Save to seo/summary document
        seo_doc_client = get_document_client(f"businesses/{business_id}/seo")

        summary_data: dict[str, Any] = {
            "overall_score": overall_score,
            "business_seo_score": business_seo_score or overall_score,
            "top_keywords": top_keywords[:10],
            "main_issues": main_issues[:5],
            "competitor_count": competitor_count,
            "competitor_avg_score": competitor_avg_score,
            "last_report_id": last_report_id,
            "last_analysis_date": timestamp,
            "updated_at": timestamp,
        }

        if serp_visibility_score is not None:
            summary_data["serp_visibility_score"] = serp_visibility_score
        if score_breakdown is not None:
            summary_data["score_breakdown"] = score_breakdown
        if geo_readiness_score is not None:
            summary_data["geo_readiness_score"] = geo_readiness_score
        if geo_analysis is not None:
            summary_data["geo_analysis"] = geo_analysis

        seo_doc_client.set_document("summary", summary_data, merge=False)

        # 2. Update agent memory with SEO info
        memory_client = get_document_client(f"businesses/{business_id}/agent_memory")

        existing_memory = memory_client.get_document("marketing") or {}

        seo_memory: dict[str, Any] = {
            "seo_score": overall_score,
            "seo_vs_competitors": f"{overall_score} vs rakip ort. {competitor_avg_score}",
            "top_seo_keywords": ", ".join(top_keywords[:5]),
            "seo_issues": "; ".join(main_issues[:3]) if main_issues else "Yok",
            "last_seo_analysis": timestamp[:10],
        }

        if serp_visibility_score is not None:
            seo_memory["serp_visibility"] = serp_visibility_score
        if geo_readiness_score is not None:
            seo_memory["geo_readiness"] = geo_readiness_score

        updated_memory = {**existing_memory, **seo_memory}
        memory_client.set_document("marketing", updated_memory, merge=True)

        # 3. Save top SEO keywords to business profile
        business_client = get_document_client("businesses")
        top_kw_for_profile = top_keywords[:7]
        business_client.set_document(
            business_id,
            {"profile": {"seo_keywords": top_kw_for_profile}},
            merge=True,
        )

        return {
            "success": True,
            "message": "SEO summary saved to seo/summary, agent_memory, and business profile",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
