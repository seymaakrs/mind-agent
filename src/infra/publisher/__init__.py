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
from .shadow import ShadowPublisher
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


def _shadow_enabled() -> bool:
    raw = (os.environ.get("PUBLISHER_SHADOW") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _build_concrete(backend: Backend, account_id: str) -> PublisherClient:
    if backend == "zernio":
        return ZernioPublisher(account_id=account_id)
    return LatePublisher(account_id=account_id)


def get_publisher(
    account_id: str,
    backend: Backend | None = None,
    shadow: bool | None = None,
) -> PublisherClient:
    """Build a publisher for one social account.

    Resolution order for ``backend``:
    1. Explicit argument (used by tests and shadow-mode comparisons).
    2. ``PUBLISHER_BACKEND`` env var (``late`` or ``zernio``).
    3. Default: ``late`` — guarantees zero behavior change until Faz 4.

    Shadow mode (``shadow=True`` or ``PUBLISHER_SHADOW=true``):
    Returns a ``ShadowPublisher`` that runs the primary backend (per
    resolution above) and the *other* backend in parallel. The primary's
    result is returned to the caller; the shadow's result is logged for
    offline comparison. Shadow failures never propagate.

    Raises ``ValueError`` when the resolved backend's credentials are not
    configured (Late's ``LATE_API_KEY`` or Zernio's ``ZERNIO_API_KEY``).
    """
    resolved = _resolve_backend(backend)
    primary = _build_concrete(resolved, account_id)

    use_shadow = shadow if shadow is not None else _shadow_enabled()
    if not use_shadow:
        return primary

    other: Backend = "zernio" if resolved == "late" else "late"
    try:
        secondary = _build_concrete(other, account_id)
    except Exception:  # noqa: BLE001 — never let shadow setup break primary
        return primary
    return ShadowPublisher(primary=primary, shadow=secondary)


__all__ = [
    "PublishResult",
    "PublisherClient",
    "LatePublisher",
    "ZernioPublisher",
    "ShadowPublisher",
    "get_publisher",
    "Backend",
]
