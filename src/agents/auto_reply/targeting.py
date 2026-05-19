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


def _build_where(now: datetime | None = None) -> str:
    """NocoDB v2 filter: bugun + auto_reply_processed=false + yon=Gelen.

    NocoDB v2 datetime sadece exactDate/daysAgo kabul ediyor; dakika
    hassasiyetli filter Python tarafinda yapilir."""
    from src.infra.nocodb_client import today_filter_clause
    now = now or datetime.now(timezone.utc)
    return (
        f"(yon,eq,Gelen)"
        f"~and(auto_reply_processed,eq,false)"
        f"~and{today_filter_clause('tarih', now)}"
    )


def find_pending_inbounds(
    client: Any,
    messages_table_id: str,
    *,
    batch_size: int,
    max_age_minutes: int,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a batch of unprocessed inbound messages, oldest first.

    NocoDB tarafi 'bugun + unprocessed' kaba pencere; max_age_minutes
    ince filter'i Python tarafinda uygulanir."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    where = _build_where(now=now)
    response = client.list_records(
        messages_table_id,
        where=where,
        limit=max(batch_size * 4, 50),  # over-fetch, sonra Python'da daralt
        sort="tarih",
    )
    rows = response.get("list") or []
    fresh = []
    for r in rows:
        ts = r.get("tarih")
        if not ts:
            continue
        try:
            # NocoDB DateTime ISO format doner (read), filter format'iyla karistirma
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if t >= cutoff:
                fresh.append(r)
        except Exception:
            continue
        if len(fresh) >= batch_size:
            break
    return fresh


__all__ = ["find_pending_inbounds", "_build_where"]
