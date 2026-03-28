from __future__ import annotations

from datetime import datetime
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


@function_tool(strict_mode=False)
async def create_weekly_plan(
    business_id: str,
    start_date: str,
    end_date: str,
    posts: list[dict[str, Any]] | None = None,
    notes: str | None = None,
    created_by: str = "agent",
) -> dict[str, Any]:
    """
    Create a weekly content plan with multiple posts.

    Args:
        business_id: Business ID.
        start_date: Plan start date in ISO format (e.g., "2025-01-06").
        end_date: Plan end date in ISO format (e.g., "2025-01-12").
        posts: List of posts to include in the plan. Each post should have:
            - scheduled_date: ISO date string
            - content_type: "image" or "reels"
            - topic: Content topic
            - brief: Content description
            - caption_draft: Optional draft caption
        notes: Optional admin notes for the plan.
        created_by: "agent" or "admin" (default "agent").

    Returns:
        dict with plan_id and post_count.
    """
    try:
        if not posts or len(posts) == 0:
            return {
                "success": False,
                "error": "posts parameter is required and must contain at least one post. Please provide a list of posts with scheduled_date, content_type, topic, and brief.",
            }

        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        plan_id = f"plan-{start_date.replace('-', '')}-{end_date.replace('-', '')}"

        processed_posts = []
        for i, post in enumerate(posts):
            processed_post = {
                "id": f"post-{i + 1}",
                "scheduled_date": post.get("scheduled_date"),
                "status": "planned",
                "content_type": post.get("content_type"),
                "topic": post.get("topic"),
                "brief": post.get("brief"),
                "caption_draft": post.get("caption_draft"),
                "generated_media_path": None,
                "instagram_post_id": None,
            }
            processed_posts.append(processed_post)

        plan_data = {
            "plan_id": plan_id,
            "start_date": start_date,
            "end_date": end_date,
            "status": "active",
            "posts": processed_posts,
            "notes": notes,
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        doc_client.set_document(plan_id, plan_data)

        return {
            "success": True,
            "plan_id": plan_id,
            "post_count": len(processed_posts),
            "message": f"Weekly plan created: {start_date} to {end_date}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_plans(
    business_id: str,
    status_filter: str | None = None,
    include_past: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Get content plans for a business.

    Args:
        business_id: Business ID.
        status_filter: Filter by plan status ("draft", "active", "paused", "completed", "cancelled").
        include_past: Include past plans (default False - only current/future).
        limit: Maximum number of plans to return.

    Returns:
        dict with plans list.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        all_plans = doc_client.list_documents(limit=100)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).date()

        filtered_plans = []
        for plan in all_plans:
            if status_filter and plan.get("status") != status_filter:
                continue

            if not include_past:
                end_date_str = plan.get("end_date")
                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str).date()
                        if end_date < today:
                            continue
                    except (ValueError, TypeError):
                        pass

            filtered_plans.append(plan)

        filtered_plans.sort(key=lambda x: x.get("start_date", ""))
        filtered_plans = filtered_plans[:limit]

        return {
            "success": True,
            "plans": filtered_plans,
            "count": len(filtered_plans),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "plans": []}


@function_tool
async def get_plan(
    business_id: str,
    plan_id: str,
) -> dict[str, Any]:
    """
    Get a specific content plan by ID.

    Args:
        business_id: Business ID.
        plan_id: Plan ID (e.g., "plan-20250106-20250112").

    Returns:
        dict with plan details.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        plan = doc_client.get_document(plan_id)

        if plan:
            return {
                "success": True,
                "found": True,
                "plan": plan,
            }
        else:
            return {
                "success": True,
                "found": False,
                "message": f"Plan not found: {plan_id}",
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def update_plan_status(
    business_id: str,
    plan_id: str,
    status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """
    Update a plan's status.

    Args:
        business_id: Business ID.
        plan_id: Plan ID.
        status: New status ("draft", "active", "paused", "completed", "cancelled").
        notes: Optional notes to add/update.

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        update_data = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
        }

        if notes is not None:
            update_data["notes"] = notes

        doc_client.set_document(plan_id, update_data, merge=True)

        return {
            "success": True,
            "plan_id": plan_id,
            "new_status": status,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def update_post_in_plan(
    business_id: str,
    plan_id: str,
    post_id: str,
    status: str | None = None,
    generated_media_path: str | None = None,
    instagram_post_id: str | None = None,
    caption_draft: str | None = None,
) -> dict[str, Any]:
    """
    Update a specific post within a plan.

    Args:
        business_id: Business ID.
        plan_id: Plan ID.
        post_id: Post ID within the plan (e.g., "post-1").
        status: New status ("planned", "created", "posted", "skipped").
        generated_media_path: Path to generated media.
        instagram_post_id: Instagram post ID after posting.
        caption_draft: Updated caption draft.

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        plan = doc_client.get_document(plan_id)
        if not plan:
            return {"success": False, "error": f"Plan not found: {plan_id}"}

        posts = plan.get("posts", [])
        post_found = False

        for post in posts:
            if post.get("id") == post_id:
                if status is not None:
                    post["status"] = status
                if generated_media_path is not None:
                    post["generated_media_path"] = generated_media_path
                if instagram_post_id is not None:
                    post["instagram_post_id"] = instagram_post_id
                if caption_draft is not None:
                    post["caption_draft"] = caption_draft
                post_found = True
                break

        if not post_found:
            return {"success": False, "error": f"Post not found: {post_id}"}

        all_done = all(p.get("status") in ("posted", "skipped") for p in posts)
        plan_status = "completed" if all_done else plan.get("status")

        update_data = {
            "posts": posts,
            "status": plan_status,
            "updated_at": datetime.now().isoformat(),
        }

        doc_client.set_document(plan_id, update_data, merge=True)

        return {
            "success": True,
            "plan_id": plan_id,
            "post_id": post_id,
            "plan_status": plan_status,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool(strict_mode=False)
async def add_post_to_plan(
    business_id: str,
    plan_id: str,
    scheduled_date: str,
    content_type: str,
    topic: str,
    brief: str,
    caption_draft: str | None = None,
) -> dict[str, Any]:
    """
    Add a new post to an existing plan.

    Args:
        business_id: Business ID.
        plan_id: Plan ID.
        scheduled_date: ISO date for the post.
        content_type: "image" or "reels".
        topic: Content topic.
        brief: Content description.
        caption_draft: Optional draft caption.

    Returns:
        dict with new post ID.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        plan = doc_client.get_document(plan_id)
        if not plan:
            return {"success": False, "error": f"Plan not found: {plan_id}"}

        posts = plan.get("posts", [])

        max_id = 0
        for post in posts:
            post_id = post.get("id", "post-0")
            try:
                num = int(post_id.split("-")[1])
                max_id = max(max_id, num)
            except (IndexError, ValueError):
                pass
        new_post_id = f"post-{max_id + 1}"

        new_post = {
            "id": new_post_id,
            "scheduled_date": scheduled_date,
            "status": "planned",
            "content_type": content_type,
            "topic": topic,
            "brief": brief,
            "caption_draft": caption_draft,
            "generated_media_path": None,
            "instagram_post_id": None,
        }

        posts.append(new_post)
        posts.sort(key=lambda x: x.get("scheduled_date", ""))

        update_data = {
            "posts": posts,
            "updated_at": datetime.now().isoformat(),
        }

        doc_client.set_document(plan_id, update_data, merge=True)

        return {
            "success": True,
            "plan_id": plan_id,
            "post_id": new_post_id,
            "post_count": len(posts),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def remove_post_from_plan(
    business_id: str,
    plan_id: str,
    post_id: str,
) -> dict[str, Any]:
    """
    Remove a post from a plan.

    Args:
        business_id: Business ID.
        plan_id: Plan ID.
        post_id: Post ID to remove.

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        plan = doc_client.get_document(plan_id)
        if not plan:
            return {"success": False, "error": f"Plan not found: {plan_id}"}

        posts = plan.get("posts", [])
        original_count = len(posts)

        posts = [p for p in posts if p.get("id") != post_id]

        if len(posts) == original_count:
            return {"success": False, "error": f"Post not found: {post_id}"}

        update_data = {
            "posts": posts,
            "updated_at": datetime.now().isoformat(),
        }

        doc_client.set_document(plan_id, update_data, merge=True)

        return {
            "success": True,
            "plan_id": plan_id,
            "removed_post_id": post_id,
            "remaining_posts": len(posts),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def get_todays_posts(
    business_id: str,
    status_filter: str | None = None,
) -> dict[str, Any]:
    """
    Get posts scheduled for today from active plans.

    Args:
        business_id: Business ID.
        status_filter: Filter by post status ("planned", "created", "posted", "skipped").

    Returns:
        dict with today's posts and their plan info.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/content_calendar")

        today = datetime.now().strftime("%Y-%m-%d")

        all_plans = doc_client.list_documents(limit=100)

        todays_posts = []
        for plan in all_plans:
            if plan.get("status") != "active":
                continue

            for post in plan.get("posts", []):
                if post.get("scheduled_date") == today:
                    if status_filter and post.get("status") != status_filter:
                        continue

                    todays_posts.append({
                        "plan_id": plan.get("plan_id"),
                        "post": post,
                    })

        return {
            "success": True,
            "date": today,
            "posts": todays_posts,
            "count": len(todays_posts),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "posts": []}
