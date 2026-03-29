from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from agents import function_tool

from src.infra.firebase_client import get_document_client


# Error collection path (root level)
ERRORS_COLLECTION = "errors"


@function_tool(
    name_override="fetch_business",
    description_override=(
        "Fetches a business profile from Firestore by business_id. "
        "Returns business info including name, colors, logo URL, website URL, profile data, "
        "instagram_id for Instagram posting, late_profile_id for Instagram analytics, "
        "youtube_id for YouTube posting, tiktok_account_id for TikTok posting, "
        "and linkedin_account_id for LinkedIn posting via Late API."
    ),
)
async def fetch_business(business_id: str) -> dict[str, Any]:
    """
    Fetch business profile from Firestore.

    Args:
        business_id: Firestore document ID in 'businesses' collection.

    Returns:
        dict: Business data including name, colors, logo, website, profile, instagram_id,
              late_profile_id (for analytics), youtube_id, tiktok_account_id, and linkedin_account_id.
    """
    doc_client = get_document_client("businesses")
    doc = doc_client.get_document(business_id)
    if doc is None:
        return {"success": False, "business_id": business_id, "error": "Business not found"}

    return {
        "success": True,
        "business_id": business_id,
        "name": doc.get("name"),
        "colors": doc.get("colors"),
        "logo": doc.get("logo"),  # Cloud Storage URL
        "website": doc.get("website"),  # Business website URL for SEO analysis
        "profile": doc.get("profile"),  # Dynamic map
        "instagram_id": doc.get("instagram_id"),  # Late API account ID (acc_xxxxx) - for POSTING
        "late_profile_id": doc.get("late_profile_id"),  # Late profile ID (raw ObjectId) - for ANALYTICS
        "youtube_id": doc.get("youtube_id"),  # Late API YouTube account ID (acc_xxxxx)
        "tiktok_account_id": doc.get("tiktok_account_id"),  # Late API TikTok account ID
        "linkedin_account_id": doc.get("linkedin_account_id"),  # Late API LinkedIn account ID
    }


@function_tool(
    name_override="report_error",
    description_override=(
        "Report an error to Firebase for admin review. "
        "Use this when you encounter an error that needs human attention. "
        "Provide clear details about what you were trying to do and what went wrong."
    ),
    strict_mode=False,
)
async def report_error(
    business_id: str,
    agent: str,
    task: str,
    error_message: str,
    error_type: Literal["api_error", "validation_error", "timeout", "rate_limit", "not_found", "permission", "unknown"] = "unknown",
    severity: Literal["low", "medium", "high", "critical"] = "medium",
    error_code: str | None = None,
    service: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Report an error to Firebase for admin/panel review.

    Args:
        business_id: Business ID where error occurred.
        agent: Which agent reported the error (e.g., "image_agent", "marketing_agent").
        task: What the agent was trying to do.
        error_message: The error message or description.
        error_type: Type of error.
        severity: Error severity (low, medium, high, critical).
        error_code: Structured error code from classify_error (e.g., "RATE_LIMIT", "CONTENT_POLICY").
        service: Which external service failed (e.g., "google_ai", "kling", "late").
        context: Additional context data (optional).

    Returns:
        dict with success status and error_id.
    """
    try:
        doc_client = get_document_client(ERRORS_COLLECTION)

        error_data = {
            "business_id": business_id,
            "agent": agent,
            "task": task,
            "error_message": error_message,
            "error_type": error_type,
            "severity": severity,
            "error_code": error_code,
            "service": service,
            "context": context,
            "created_at": datetime.now().isoformat(),
            "resolved": False,
            "resolved_at": None,
            "resolution_note": None,
        }

        result = doc_client.add_document(error_data)
        error_id = result.get("documentId")

        return {
            "success": True,
            "error_id": error_id,
            "message": "Error reported successfully. Admin will review.",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to report error: {e}"}
