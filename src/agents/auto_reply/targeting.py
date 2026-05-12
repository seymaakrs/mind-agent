"""NocoDB queries for Auto-reply Agent.

Picks Etkilesimler rows where:
    yon                   = 'Gelen'
    auto_reply_processed  = false
    tarih                 > now - max_inbound_age_minutes

Oldest first (FIFO). Worker iterates the batch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _build_where(max_age_minutes: int, now: datetime | None = None) -> str:
    from src.infra.nocodb_client import iso_for_nocodb_filter
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=max_age_minutes)
    return (
        f"(yon,eq,Gelen)"
        f"~and(auto_reply_processed,eq,false)"
        f"~and(tarih,gt,{iso_for_nocodb_filter(cutoff)})"
    )


def find_pending_inbounds(
    client: Any,
    messages_table_id: str,
    *,
    batch_size: int,
    max_age_minutes: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a batch of unprocessed inbound messages, oldest first."""
    where = _build_where(max_age_minutes, now=now)
    response = client.list_records(
        messages_table_id,
        where=where,
        limit=batch_size,
        sort="tarih",
    )
    return list(response.get("list") or [])


__all__ = ["find_pending_inbounds", "_build_where"]
