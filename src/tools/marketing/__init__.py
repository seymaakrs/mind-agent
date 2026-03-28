"""Marketing tools package — calendar, media tracking, and agent memory tools."""

from .calendar import (
    create_weekly_plan,
    get_plans,
    get_plan,
    update_plan_status,
    update_post_in_plan,
    add_post_to_plan,
    remove_post_from_plan,
    get_todays_posts,
)
from .media_tracking import (
    save_instagram_post,
    get_instagram_posts,
    get_post_by_instagram_id,
    save_youtube_video,
    get_youtube_videos,
    get_youtube_video_by_id,
)
from .memory import (
    get_marketing_memory,
    update_marketing_memory,
    schedule_retry_job,
    get_admin_notes,
    add_admin_note,
    remove_admin_note,
    compact_marketing_memory,
    clear_marketing_memory,
)


def get_marketing_tools() -> list:
    """Return list of marketing-specific tools for the agent."""
    return [
        # Calendar (Plan-Based)
        create_weekly_plan,
        get_plans,
        get_plan,
        update_plan_status,
        update_post_in_plan,
        add_post_to_plan,
        remove_post_from_plan,
        get_todays_posts,
        # Instagram posts
        save_instagram_post,
        get_instagram_posts,
        get_post_by_instagram_id,
        # YouTube videos
        save_youtube_video,
        get_youtube_videos,
        get_youtube_video_by_id,
        # Memory
        get_marketing_memory,
        update_marketing_memory,
        # Job scheduling
        schedule_retry_job,
    ]


def get_admin_tools() -> list:
    """Return list of admin-only tools (for panel/API, NOT for agent)."""
    return [
        get_admin_notes,
        add_admin_note,
        remove_admin_note,
        compact_marketing_memory,
        clear_marketing_memory,
    ]


__all__ = [
    # Calendar
    "create_weekly_plan", "get_plans", "get_plan", "update_plan_status",
    "update_post_in_plan", "add_post_to_plan", "remove_post_from_plan", "get_todays_posts",
    # Media tracking
    "save_instagram_post", "get_instagram_posts", "get_post_by_instagram_id",
    "save_youtube_video", "get_youtube_videos", "get_youtube_video_by_id",
    # Memory
    "get_marketing_memory", "update_marketing_memory", "schedule_retry_job",
    # Admin
    "get_admin_notes", "add_admin_note", "remove_admin_note",
    "compact_marketing_memory", "clear_marketing_memory",
    # Tool lists
    "get_marketing_tools", "get_admin_tools",
]
