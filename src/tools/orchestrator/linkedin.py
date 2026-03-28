from __future__ import annotations

from typing import Any, Literal

from agents import function_tool

from src.infra.firebase_client import get_document_client
from src.infra.late_client import get_late_client


@function_tool(
    name_override="post_on_linkedin",
    description_override=(
        "Post to LinkedIn via Late API (text-only, single image, or video).\n\n"
        "Automatically fetches linkedin_account_id from the business profile in Firebase.\n\n"
        "SCENARIOS:\n"
        "1. Text-only: Provide only content (no media_url)\n"
        "2. Image post: Provide content + media_url + media_type='image'\n"
        "3. Video post: Provide content + media_url + media_type='video'\n\n"
        "REQUIRED:\n"
        "- business_id: Business ID to fetch linkedin_account_id from Firebase\n"
        "- content: Post text (max 3000 chars). Optional only if media_url provided.\n\n"
        "OPTIONAL:\n"
        "- media_url: Public URL of image or video\n"
        "- media_type: 'image' or 'video' (required if media_url provided)\n"
        "- first_comment: Auto-posted first comment (recommended for links - LinkedIn suppresses posts with URLs by 40-50%%)\n"
        "- disable_link_preview: Suppress URL preview card (default: false)\n"
        "- organization_urn: Post as company page (format: urn:li:organization:XXXXX)\n"
        "- scheduled_for: ISO datetime for scheduled post"
    ),
    strict_mode=False,
)
async def post_on_linkedin(
    business_id: str,
    content: str | None = None,
    media_url: str | None = None,
    media_type: Literal["image", "video"] | None = None,
    first_comment: str | None = None,
    disable_link_preview: bool | None = None,
    organization_urn: str | None = None,
    scheduled_for: str | None = None,
) -> dict[str, Any]:
    """
    Post to LinkedIn via Late API.

    Args:
        business_id: Business ID to fetch linkedin_account_id from Firebase.
        content: Post text (max 3000 chars).
        media_url: Public URL of image or video (optional).
        media_type: "image" or "video" (required if media_url provided).
        first_comment: Auto-posted first comment (optional).
        disable_link_preview: Suppress URL preview card (optional).
        organization_urn: Post as company page (optional).
        scheduled_for: ISO datetime for scheduled post (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if not content and not media_url:
            return {
                "success": False,
                "error": "Either content or media_url must be provided",
            }

        if content and len(content) > 3000:
            return {
                "success": False,
                "error": f"Content exceeds 3000 characters ({len(content)} chars)",
            }

        if media_url and not media_type:
            return {
                "success": False,
                "error": "media_type is required when media_url is provided. Use 'image' or 'video'.",
            }

        if media_url and not media_url.startswith("http"):
            return {
                "success": False,
                "error": f"Invalid media URL '{media_url}'. URL must start with http:// or https://",
            }

        # --- Fetch linkedin_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        linkedin_account_id = business.get("linkedin_account_id")
        if not linkedin_account_id:
            return {
                "success": False,
                "error": f"No linkedin_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(linkedin_account_id)
        result = await late.post_linkedin(
            content=content,
            media_url=media_url,
            media_type=media_type,
            first_comment=first_comment,
            disable_link_preview=disable_link_preview,
            organization_urn=organization_urn,
            scheduled_for=scheduled_for,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
            }

        content_type = media_type or "text"
        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": content_type,
            "message": f"Successfully posted {content_type} to LinkedIn",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"LinkedIn posting failed: {type(exc).__name__}: {exc}",
        }


@function_tool(
    name_override="post_carousel_on_linkedin",
    description_override=(
        "Post a multi-image carousel (2-20 images) to LinkedIn via Late API.\n\n"
        "Automatically fetches linkedin_account_id from the business profile in Firebase.\n\n"
        "REQUIRED:\n"
        "- media_items: List of 2-20 image objects. Each must have 'url' and 'type': 'image'\n"
        "- business_id: Business ID to fetch linkedin_account_id from Firebase\n\n"
        "OPTIONAL:\n"
        "- content: Post text (max 3000 chars)\n"
        "- first_comment: Auto-posted first comment\n"
        "- disable_link_preview: Suppress URL preview card\n"
        "- organization_urn: Post as company page (format: urn:li:organization:XXXXX)\n"
        "- scheduled_for: ISO datetime for scheduled post\n\n"
        "NOTE: Cannot mix media types. All items must be images."
    ),
    strict_mode=False,
)
async def post_carousel_on_linkedin(
    media_items: list[dict],
    business_id: str,
    content: str | None = None,
    first_comment: str | None = None,
    disable_link_preview: bool | None = None,
    organization_urn: str | None = None,
    scheduled_for: str | None = None,
) -> dict[str, Any]:
    """
    Post a multi-image carousel to LinkedIn via Late API.

    Args:
        media_items: List of image items (2-20).
        business_id: Business ID to fetch linkedin_account_id from Firebase.
        content: Post text (max 3000 chars, optional).
        first_comment: Auto-posted first comment (optional).
        disable_link_preview: Suppress URL preview card (optional).
        organization_urn: Post as company page (optional).
        scheduled_for: ISO datetime for scheduled post (optional).

    Returns:
        dict with success, post_id, and details.
    """
    try:
        # --- Validations ---
        if len(media_items) < 2:
            return {
                "success": False,
                "error": "LinkedIn carousel requires at least 2 media items",
            }

        if len(media_items) > 20:
            return {
                "success": False,
                "error": "LinkedIn carousel cannot have more than 20 media items",
            }

        if content and len(content) > 3000:
            return {
                "success": False,
                "error": f"Content exceeds 3000 characters ({len(content)} chars)",
            }

        for i, item in enumerate(media_items):
            if not isinstance(item, dict):
                return {
                    "success": False,
                    "error": f"media_items[{i}] must be a dict, got {type(item).__name__}",
                }
            url = item.get("url")
            if not url:
                return {
                    "success": False,
                    "error": f"media_items[{i}] missing required 'url' field",
                }
            if not url.startswith("http"):
                return {
                    "success": False,
                    "error": f"media_items[{i}] has invalid URL '{url}'. URL must start with http:// or https://",
                }

        # --- Fetch linkedin_account_id from Firebase ---
        doc_client = get_document_client("businesses")
        business = doc_client.get_document(business_id)

        if business is None:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }

        linkedin_account_id = business.get("linkedin_account_id")
        if not linkedin_account_id:
            return {
                "success": False,
                "error": f"No linkedin_account_id found for business {business_id}. Please add it to the business profile.",
            }

        # --- Post via Late API ---
        late = get_late_client(linkedin_account_id)
        result = await late.post_linkedin_carousel(
            media_items=media_items,
            content=content,
            first_comment=first_comment,
            disable_link_preview=disable_link_preview,
            organization_urn=organization_urn,
            scheduled_for=scheduled_for,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "status_code": result.get("status_code"),
                "item_count": len(media_items),
            }

        return {
            "success": True,
            "post_id": result.get("platform_post_id"),
            "late_post_id": result.get("post_id"),
            "post_url": result.get("platform_post_url"),
            "content_type": "carousel",
            "item_count": result.get("item_count"),
            "message": f"Successfully posted carousel with {result.get('item_count')} images to LinkedIn",
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"LinkedIn carousel posting failed: {type(exc).__name__}: {exc}",
            "item_count": len(media_items),
        }
