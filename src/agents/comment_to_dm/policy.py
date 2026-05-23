"""Per-business config + idempotency policy for Comment-to-DM.

Firestore path: ``businesses/{id}/comment_to_dm/config``

Fields:
    enabled                 (bool, default False — opt-in)
    pricing_template        (str|None, optional override for sales DM)
    whitelist_keywords      (list[str]) — if set, only fire when comment
                            contains one of these
    blacklist_keywords      (list[str]) — never fire if any present
    max_dms_per_day         (int, default 50)
    thank_you_enabled       (bool, default False) — like + thank-you DM
                            for compliments

Idempotency: ``businesses/{id}/comment_to_dm/sent/{post_id}__{author_id}``
records ``sent_at`` ISO; we skip if within 24h.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class CommentToDMConfig:
    enabled: bool = False
    pricing_template: str | None = None
    whitelist_keywords: tuple[str, ...] = ()
    blacklist_keywords: tuple[str, ...] = ()
    max_dms_per_day: int = 50
    thank_you_enabled: bool = False

    @classmethod
    def from_doc(cls, doc: dict[str, Any] | None) -> "CommentToDMConfig":
        doc = doc or {}
        return cls(
            enabled=bool(doc.get("enabled", False)),
            pricing_template=doc.get("pricing_template") or None,
            whitelist_keywords=tuple(doc.get("whitelist_keywords") or ()),
            blacklist_keywords=tuple(doc.get("blacklist_keywords") or ()),
            max_dms_per_day=int(doc.get("max_dms_per_day") or 50),
            thank_you_enabled=bool(doc.get("thank_you_enabled", False)),
        )


def keyword_check(text: str, cfg: CommentToDMConfig) -> tuple[bool, str]:
    """Apply whitelist/blacklist gates. Returns ``(allowed, reason)``."""
    lower = (text or "").lower()
    for bad in cfg.blacklist_keywords:
        if bad and bad.lower() in lower:
            return False, f"blacklist hit: {bad}"
    if cfg.whitelist_keywords:
        if not any(w.lower() in lower for w in cfg.whitelist_keywords if w):
            return False, "no whitelist keyword matched"
    return True, "ok"


def already_dm_d_recently(
    sent_at_iso: str | None, *, hours: int = 24
) -> bool:
    """Return True if ``sent_at_iso`` is within the last ``hours``."""
    if not sent_at_iso:
        return False
    try:
        ts = datetime.fromisoformat(sent_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - ts < timedelta(hours=hours)


__all__ = [
    "CommentToDMConfig",
    "keyword_check",
    "already_dm_d_recently",
]
