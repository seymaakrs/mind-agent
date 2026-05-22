"""Zernio API client (https://api.zernio.com/v1).

Zernio aggregates multiple channels (WhatsApp Business, Inbox, Social) behind
one HTTP API. This package only ships the WhatsApp + Inbox surface that the
Slowdays cold-outreach playbook needs (Adim 2 of the Sales roadmap):

- ``whatsapp/contacts`` — list / paginate WA contacts
- ``inbox/conversations`` — find a thread by phone number
- ``inbox/conversations/{id}/messages`` — send a free-form reply
- ``contacts/{id}`` — patch tags (CRM segmentation)

Mixin composition keeps each concern (WhatsApp, Inbox, Posts, Media,
Analytics) in its own file so additional surfaces (e.g. comment-to-DM,
sequences) can be added without bloating one module.
"""
from __future__ import annotations

from .base import _ZernioBase
from .whatsapp import _WhatsAppMixin
from .inbox import _InboxMixin
from .posts import _PostsMixin
from .media import _MediaMixin
from .analytics import _AnalyticsMixin
from .logs import _LogsMixin


class ZernioClient(
    _WhatsAppMixin,
    _InboxMixin,
    _PostsMixin,
    _MediaMixin,
    _AnalyticsMixin,
    _LogsMixin,
    _ZernioBase,
):
    """Async HTTP client over the Zernio v1 API.

    Errors bubble up as ``ServiceError`` with status_code + service set, so
    tool wrappers can run them through ``classify_error(exc, "zernio")``.
    """

    pass


def get_zernio_client() -> ZernioClient:
    """Build a ZernioClient from settings.

    Reads ``ZERNIO_API_KEY``, ``ZERNIO_BASE_URL``, ``ZERNIO_WA_ACCOUNT_ID``
    via ``src.app.config.get_settings()``. Raises ``ValueError`` when the
    API key is missing — matches the Late client contract.
    """
    from src.app.config import get_settings

    settings = get_settings()
    if not settings.zernio_api_key:
        raise ValueError("ZERNIO_API_KEY is not configured")

    return ZernioClient(
        api_key=settings.zernio_api_key,
        account_id=settings.zernio_wa_account_id,
        base_url=settings.zernio_base_url,
    )


__all__ = ["ZernioClient", "get_zernio_client"]
