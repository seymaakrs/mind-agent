"""Shadow-mode wrapper for the Publisher layer.

Runs two backends in parallel for one call: the **primary** result is
returned to the caller (so production behavior is unchanged), and the
**shadow** result is computed concurrently and a diff is logged for
offline comparison. Any exception in the shadow path is swallowed —
shadow MUST NOT affect the user-facing call.

This is the bridge that lets us compare Late vs Zernio on real
production traffic before flipping the backend default.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .base import PublishResult, PublisherClient

log = logging.getLogger("publisher.shadow")


class ShadowPublisher:
    """Run two ``PublisherClient`` adapters in parallel.

    Caller receives ``primary``'s result. ``shadow``'s result (or
    exception) is logged with a structured diff but never raised.
    """

    def __init__(self, primary: PublisherClient, shadow: PublisherClient) -> None:
        self._primary = primary
        self._shadow = shadow

    # Surface attributes (PublisherClient Protocol fields) ---------------

    @property
    def backend(self) -> str:
        return f"shadow({self._primary.backend}→{self._shadow.backend})"

    @property
    def account_id(self) -> str:
        return self._primary.account_id

    # Internal -----------------------------------------------------------

    async def _run(
        self,
        method_name: str,
        kwargs: dict[str, Any],
    ) -> PublishResult:
        primary_call: Callable[..., Awaitable[PublishResult]] = getattr(
            self._primary, method_name
        )
        shadow_call: Callable[..., Awaitable[PublishResult]] = getattr(
            self._shadow, method_name
        )

        # gather(return_exceptions=True) so an exploding shadow does not
        # cancel the primary's coroutine via the implicit task cancellation
        # rules of asyncio.gather. Latency cost: max(primary, shadow) —
        # NOT the sum — since both run concurrently. If shadow latency
        # ever exceeds primary's by a margin worth bounding, swap this
        # for create_task + done_callback (fire-and-forget) in Faz 4.
        primary_result, shadow_outcome = await asyncio.gather(
            primary_call(**kwargs),
            _safe(shadow_call, kwargs),
            return_exceptions=True,
        )

        if isinstance(primary_result, BaseException):
            # Primary failure must propagate exactly as before.
            log.warning(
                "primary backend %s raised on %s: %r",
                self._primary.backend,
                method_name,
                primary_result,
            )
            raise primary_result

        _log_diff(
            method=method_name,
            account_id=self.account_id,
            primary=primary_result,
            primary_backend=self._primary.backend,
            shadow_outcome=shadow_outcome,
            shadow_backend=self._shadow.backend,
        )
        return primary_result

    # Publisher surface --------------------------------------------------
    # Each method just forwards to _run; no business logic here.

    async def instagram_post(self, **kw: Any) -> PublishResult:
        return await self._run("instagram_post", kw)

    async def instagram_carousel(self, **kw: Any) -> PublishResult:
        return await self._run("instagram_carousel", kw)

    async def linkedin_post(self, **kw: Any) -> PublishResult:
        return await self._run("linkedin_post", kw)

    async def linkedin_carousel(self, **kw: Any) -> PublishResult:
        return await self._run("linkedin_carousel", kw)

    async def tiktok_video(self, **kw: Any) -> PublishResult:
        return await self._run("tiktok_video", kw)

    async def tiktok_carousel(self, **kw: Any) -> PublishResult:
        return await self._run("tiktok_carousel", kw)

    async def youtube_video(self, **kw: Any) -> PublishResult:
        return await self._run("youtube_video", kw)


# Helpers --------------------------------------------------------------------


async def _safe(
    call: Callable[..., Awaitable[PublishResult]],
    kwargs: dict[str, Any],
) -> PublishResult | BaseException:
    """Run ``call(**kwargs)`` and capture any exception as a value.

    Returning the exception (rather than raising) lets ``asyncio.gather``
    treat both tasks uniformly and gives ``_log_diff`` a structured record
    of the shadow failure mode.
    """
    try:
        return await call(**kwargs)
    except BaseException as exc:  # noqa: BLE001 — shadow must never raise
        return exc


def _log_diff(
    *,
    method: str,
    account_id: str,
    primary: PublishResult,
    primary_backend: str,
    shadow_outcome: PublishResult | BaseException,
    shadow_backend: str,
) -> None:
    if isinstance(shadow_outcome, BaseException):
        log.warning(
            "publisher.shadow method=%s account=%s primary=%s/%s shadow=%s/EXC %r",
            method,
            account_id,
            primary_backend,
            "ok" if primary.success else f"fail:{primary.status_code}",
            shadow_backend,
            shadow_outcome,
        )
        return

    diff = _diff(primary, shadow_outcome)
    if diff:
        log.warning(
            "publisher.shadow method=%s account=%s diff=%s primary=%s shadow=%s",
            method,
            account_id,
            diff,
            _summary(primary),
            _summary(shadow_outcome),
        )
    else:
        log.info(
            "publisher.shadow method=%s account=%s parity=ok",
            method,
            account_id,
        )


def _summary(r: PublishResult) -> dict[str, Any]:
    return {
        "success": r.success,
        "status": r.status,
        "platform_post_id": r.platform_post_id,
        "status_code": r.status_code,
        "error": r.error,
    }


def _diff(a: PublishResult, b: PublishResult) -> list[str]:
    """Return field names that disagree at a coarse level.

    We intentionally compare *categorical* fields (success, status,
    presence of platform_post_id) instead of exact IDs — the two
    backends mint different ``post_id`` / ``platform_post_id`` values
    even for equivalent posts.
    """
    out: list[str] = []
    if a.success != b.success:
        out.append("success")
    if a.status != b.status:
        out.append("status")
    if bool(a.platform_post_id) != bool(b.platform_post_id):
        out.append("platform_post_id_presence")
    if a.success is False and a.status_code != b.status_code:
        out.append("status_code")
    return out
