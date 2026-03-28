from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from agents import function_tool

from src.infra.firebase_client import get_document_client


# Memory size thresholds for auto-compact
PATTERNS_THRESHOLD = 50
NOTES_THRESHOLD = 100
PATTERNS_KEEP = 20
NOTES_KEEP = 30


@function_tool
async def get_marketing_memory(
    business_id: str,
) -> dict[str, Any]:
    """
    Get the marketing agent's memory for a business.

    This memory contains learned patterns, business understanding,
    content insights, and admin notes that persist across sessions.

    IMPORTANT: Always check admin_notes first - these are mandatory guidelines!

    Args:
        business_id: Business ID.

    Returns:
        dict with memory contents including admin_notes.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        memory = doc_client.get_document("marketing")

        if memory:
            return {
                "success": True,
                "has_memory": True,
                "memory": memory,
            }
        else:
            return {
                "success": True,
                "has_memory": False,
                "memory": {
                    "business_understanding": {
                        "summary": None,
                        "strengths": [],
                        "audience": None,
                        "voice_tone": None,
                    },
                    "content_insights": {
                        "best_performing_types": [],
                        "best_posting_times": [],
                        "effective_hashtags": [],
                        "caption_styles_that_work": [],
                    },
                    "learned_patterns": [],
                    "notes": [],
                    "admin_notes": [],
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool(strict_mode=False)
async def update_marketing_memory(
    business_id: str,
    business_understanding: dict[str, Any] | None = None,
    content_insights: dict[str, Any] | None = None,
    new_pattern: str | None = None,
    new_note: str | None = None,
) -> dict[str, Any]:
    """
    Update the marketing agent's memory for a business.

    Auto-compacts when memory gets too large (>50 patterns or >100 notes).

    Args:
        business_id: Business ID.
        business_understanding: Update business understanding fields (merged).
        content_insights: Update content insights fields (merged).
        new_pattern: Add a new learned pattern.
        new_note: Add a new note.

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        existing = doc_client.get_document("marketing") or {
            "business_understanding": {},
            "content_insights": {},
            "learned_patterns": [],
            "notes": [],
            "admin_notes": [],
        }

        if business_understanding:
            existing["business_understanding"] = {
                **existing.get("business_understanding", {}),
                **business_understanding,
            }

        if content_insights:
            existing["content_insights"] = {
                **existing.get("content_insights", {}),
                **content_insights,
            }

        if new_pattern:
            patterns = existing.get("learned_patterns", [])
            if new_pattern not in patterns:
                patterns.append(new_pattern)
                existing["learned_patterns"] = patterns

        if new_note:
            notes = existing.get("notes", [])
            notes.append({
                "note": new_note,
                "added_at": datetime.now().isoformat(),
            })
            existing["notes"] = notes

        # Auto-compact if thresholds exceeded
        compacted = False
        patterns = existing.get("learned_patterns", [])
        notes = existing.get("notes", [])

        if len(patterns) > PATTERNS_THRESHOLD:
            existing["learned_patterns"] = patterns[-PATTERNS_KEEP:]
            compacted = True

        if len(notes) > NOTES_THRESHOLD:
            existing["notes"] = notes[-NOTES_KEEP:]
            compacted = True

        if compacted:
            existing["last_compacted"] = datetime.now().isoformat()

        existing["last_updated"] = datetime.now().isoformat()

        doc_client.set_document("marketing", existing)

        result = {
            "success": True,
            "message": "Marketing memory updated",
        }

        if compacted:
            result["auto_compacted"] = True
            result["patterns_count"] = len(existing["learned_patterns"])
            result["notes_count"] = len(existing["notes"])

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Job Scheduling (Retry/Planned Jobs)
# =============================================================================

@function_tool
async def schedule_retry_job(
    business_id: str,
    task: str,
    delay_minutes: int = 15,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Schedule a retry job for later execution. Use this when you encounter
    rate limits, quota errors, or temporary failures.

    The job will be picked up by Cloud Functions after the delay period.

    Args:
        business_id: Business ID.
        task: The FULL original task text to retry.
        delay_minutes: Minutes to wait before retry (default 15).
        reason: Optional reason for scheduling the retry.

    Returns:
        dict with job_id and scheduled time.
    """
    try:
        from datetime import timezone
        doc_client = get_document_client(f"businesses/{business_id}/jobs")

        now = datetime.now(timezone.utc)
        scheduled_at = now + timedelta(minutes=delay_minutes)

        job_data = {
            "businessId": business_id,
            "task": task,
            "type": "planned",
            "isExecuted": False,
            "createdAt": now.isoformat(),
            "scheduledAt": scheduled_at.isoformat(),
            "executedAt": None,
            "reason": reason,
        }

        result = doc_client.add_document(job_data)

        return {
            "success": True,
            "job_id": result["documentId"],
            "scheduled_at": scheduled_at.isoformat(),
            "delay_minutes": delay_minutes,
            "message": f"Retry job scheduled for {delay_minutes} minutes later",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Admin Notes (Mandatory Guidelines for Agent)
# =============================================================================

@function_tool
async def get_admin_notes(
    business_id: str,
) -> dict[str, Any]:
    """
    Get admin notes for a business. These are mandatory guidelines the agent MUST follow.

    Admin notes contain rules like:
    - "Only create content about technology topics"
    - "Never use emojis in captions"
    - "Always include brand hashtag #TechBrand"

    Args:
        business_id: Business ID.

    Returns:
        dict with admin notes list.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        memory = doc_client.get_document("marketing")

        admin_notes = memory.get("admin_notes", []) if memory else []

        return {
            "success": True,
            "admin_notes": admin_notes,
            "count": len(admin_notes),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "admin_notes": []}


@function_tool
async def add_admin_note(
    business_id: str,
    note: str,
    priority: str = "normal",
) -> dict[str, Any]:
    """
    Add an admin note (mandatory guideline) for the marketing agent.

    These notes are ALWAYS shown to the agent and must be followed.

    Args:
        business_id: Business ID.
        note: The guideline/rule to add.
        priority: "high", "normal", or "low" (high priority notes shown first).

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        existing = doc_client.get_document("marketing") or {
            "business_understanding": {},
            "content_insights": {},
            "learned_patterns": [],
            "notes": [],
            "admin_notes": [],
        }

        admin_notes = existing.get("admin_notes", [])

        new_note = {
            "note": note,
            "priority": priority,
            "added_at": datetime.now().isoformat(),
            "active": True,
        }

        admin_notes.append(new_note)

        priority_order = {"high": 0, "normal": 1, "low": 2}
        admin_notes.sort(key=lambda x: priority_order.get(x.get("priority", "normal"), 1))

        existing["admin_notes"] = admin_notes
        existing["last_updated"] = datetime.now().isoformat()

        doc_client.set_document("marketing", existing)

        return {
            "success": True,
            "message": "Admin note added",
            "total_notes": len(admin_notes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def remove_admin_note(
    business_id: str,
    note_index: int,
) -> dict[str, Any]:
    """
    Remove an admin note by index.

    Args:
        business_id: Business ID.
        note_index: Index of the note to remove (0-based).

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        existing = doc_client.get_document("marketing")
        if not existing:
            return {"success": False, "error": "No memory found"}

        admin_notes = existing.get("admin_notes", [])

        if note_index < 0 or note_index >= len(admin_notes):
            return {"success": False, "error": f"Invalid index: {note_index}"}

        removed = admin_notes.pop(note_index)
        existing["admin_notes"] = admin_notes
        existing["last_updated"] = datetime.now().isoformat()

        doc_client.set_document("marketing", existing)

        return {
            "success": True,
            "removed_note": removed.get("note"),
            "remaining_notes": len(admin_notes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Memory Compaction
# =============================================================================

@function_tool
async def compact_marketing_memory(
    business_id: str,
    keep_patterns: int = 20,
    keep_notes: int = 30,
) -> dict[str, Any]:
    """
    Compact the marketing memory by keeping only recent/important entries.

    This removes old learned_patterns and notes to prevent memory bloat.
    Admin notes are NEVER removed by this function.

    Args:
        business_id: Business ID.
        keep_patterns: Number of recent patterns to keep (default 20).
        keep_notes: Number of recent notes to keep (default 30).

    Returns:
        dict with compaction stats.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        existing = doc_client.get_document("marketing")
        if not existing:
            return {"success": True, "message": "No memory to compact"}

        old_patterns = len(existing.get("learned_patterns", []))
        old_notes = len(existing.get("notes", []))

        patterns = existing.get("learned_patterns", [])
        existing["learned_patterns"] = patterns[-keep_patterns:] if len(patterns) > keep_patterns else patterns

        notes = existing.get("notes", [])
        existing["notes"] = notes[-keep_notes:] if len(notes) > keep_notes else notes

        existing["last_compacted"] = datetime.now().isoformat()
        existing["last_updated"] = datetime.now().isoformat()

        doc_client.set_document("marketing", existing)

        return {
            "success": True,
            "patterns_before": old_patterns,
            "patterns_after": len(existing["learned_patterns"]),
            "notes_before": old_notes,
            "notes_after": len(existing["notes"]),
            "admin_notes_preserved": len(existing.get("admin_notes", [])),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@function_tool
async def clear_marketing_memory(
    business_id: str,
    keep_admin_notes: bool = True,
) -> dict[str, Any]:
    """
    Clear all marketing memory (reset to empty state).

    WARNING: This removes all learned patterns, notes, and insights.

    Args:
        business_id: Business ID.
        keep_admin_notes: If True, admin notes are preserved (default True).

    Returns:
        dict with success status.
    """
    try:
        doc_client = get_document_client(f"businesses/{business_id}/agent_memory")

        admin_notes = []
        if keep_admin_notes:
            existing = doc_client.get_document("marketing")
            if existing:
                admin_notes = existing.get("admin_notes", [])

        fresh_memory = {
            "business_understanding": {
                "summary": None,
                "strengths": [],
                "audience": None,
                "voice_tone": None,
            },
            "content_insights": {
                "best_performing_types": [],
                "best_posting_times": [],
                "effective_hashtags": [],
                "caption_styles_that_work": [],
            },
            "learned_patterns": [],
            "notes": [],
            "admin_notes": admin_notes,
            "last_updated": datetime.now().isoformat(),
            "cleared_at": datetime.now().isoformat(),
        }

        doc_client.set_document("marketing", fresh_memory)

        return {
            "success": True,
            "message": "Marketing memory cleared",
            "admin_notes_preserved": len(admin_notes),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
