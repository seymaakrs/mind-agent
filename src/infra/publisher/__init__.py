"""Publisher adapter layer.

After the Late→Zernio migration (Faz 6) Zernio is the only supported
backend. The Protocol, ``PublishResult``, and the ``get_publisher``
factory are kept as the public seam so a future second backend can
plug in without churning the tool layer.

``PUBLISHER_BACKEND`` env values:

- ``zernio`` (default): use Zernio
- ``late``: raises a clear error. Late was removed in Faz 6.
- anything else: treated as ``zernio``
"""
from __future__ import annotations

import os
from typing import Literal

from .base import PublishResult, PublisherClient
from .zernio_publisher import ZernioPublisher


Backend = Literal["zernio"]

_DEFAULT_BACKEND: Backend = "zernio"


def _resolve_backend(explicit: str | None) -> Backend:
    if explicit is not None:
        raw = explicit.strip().lower()
    else:
        raw = (os.environ.get("PUBLISHER_BACKEND") or "").strip().lower()
    if raw == "late":
        raise ValueError(
            "PUBLISHER_BACKEND=late is no longer supported. The Late "
            "client was removed in Faz 6 of the Late→Zernio migration. "
            "Set PUBLISHER_BACKEND=zernio (or leave unset) and ensure "
            "ZERNIO_API_KEY is configured."
        )
    return _DEFAULT_BACKEND


def get_publisher(
    account_id: str,
    backend: str | None = None,
) -> PublisherClient:
    """Build a publisher for one social account.

    Currently always returns ``ZernioPublisher``. The ``backend`` kwarg
    is retained for forward compatibility; ``"late"`` raises explicitly.
    """
    _resolve_backend(backend)  # validates; raises on "late"
    return ZernioPublisher(account_id=account_id)


__all__ = [
    "PublishResult",
    "PublisherClient",
    "ZernioPublisher",
    "get_publisher",
    "Backend",
]
