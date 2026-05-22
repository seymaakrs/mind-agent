"""Publisher adapter layer — backend-agnostic social posting.

Tool code targets ``PublisherClient`` (a Protocol), not a concrete client.
The factory ``get_publisher(account_id, backend=None)`` returns either
``LatePublisher`` or ``ZernioPublisher`` depending on the
``PUBLISHER_BACKEND`` env var.

This module is the bridge that lets us flip the backend behind a feature
flag in Faz 3, channel by channel, with zero call-site changes.
"""
from __future__ import annotations

import os
from typing import Literal

from .base import PublishResult, PublisherClient
from .late_publisher import LatePublisher
from .zernio_publisher import ZernioPublisher


Backend = Literal["late", "zernio"]

_DEFAULT_BACKEND: Backend = "late"


def _resolve_backend(explicit: Backend | None) -> Backend:
    if explicit is not None:
        return explicit
    raw = (os.environ.get("PUBLISHER_BACKEND") or "").strip().lower()
    if raw in ("late", "zernio"):
        return raw  # type: ignore[return-value]
    return _DEFAULT_BACKEND


def get_publisher(
    account_id: str,
    backend: Backend | None = None,
) -> PublisherClient:
    """Build a publisher for one social account.

    Resolution order for ``backend``:
    1. Explicit argument (used by tests and shadow-mode comparisons).
    2. ``PUBLISHER_BACKEND`` env var (``late`` or ``zernio``).
    3. Default: ``late`` — guarantees zero behavior change until Faz 3.

    Raises ``ValueError`` when the resolved backend's credentials are not
    configured (Late's ``LATE_API_KEY`` or Zernio's ``ZERNIO_API_KEY``).
    """
    resolved = _resolve_backend(backend)
    if resolved == "zernio":
        return ZernioPublisher(account_id=account_id)
    return LatePublisher(account_id=account_id)


__all__ = [
    "PublishResult",
    "PublisherClient",
    "LatePublisher",
    "ZernioPublisher",
    "get_publisher",
    "Backend",
]
