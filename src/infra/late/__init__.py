"""Late API client package — split by platform for maintainability."""

from .base import _LateBase
from .instagram import _InstagramMixin
from .tiktok import _TikTokMixin
from .linkedin import _LinkedInMixin
from .youtube import _YouTubeMixin


class LateClient(_InstagramMixin, _TikTokMixin, _LinkedInMixin, _YouTubeMixin, _LateBase):
    """Client for Late API (Instagram/TikTok/LinkedIn/YouTube posting service).

    Composes platform-specific mixins on top of the base HTTP client.
    MRO ensures _LateBase.__init__ and _get_headers are available to all mixins.
    """

    pass


def get_late_client(account_id: str, strip_prefix: bool = True) -> LateClient:
    """
    Create LateClient instance with API key from config.

    Args:
        account_id: Late account ID (acc_xxxxx for posting, raw ObjectId for analytics).
        strip_prefix: If True, strips "acc_" prefix (for posting).
                      If False, uses ID as-is (for analytics with late_profile_id).

    Returns:
        LateClient instance.

    Raises:
        ValueError: If LATE_API_KEY is not configured.
    """
    from src.app.config import get_settings

    settings = get_settings()
    if not settings.late_api_key:
        raise ValueError("LATE_API_KEY is not configured")

    if strip_prefix and account_id.startswith("acc_"):
        account_id = account_id[4:]

    return LateClient(settings.late_api_key, account_id)


__all__ = ["LateClient", "get_late_client"]
