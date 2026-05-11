"""NocoDB target picker for Outreach Agent.

Filter contract:
    source_workflow_id = OutreachConfig.source_workflow_id  (default 'outreach_agent_v1')
    asama              = 'Yeni'  (henuz mesaj atilmadi)
    telefon            != ''     (mesaj atilabilir bir hat)

Why ``source_workflow_id`` (not ``kaynak``)?
- ``kaynak`` is "how the lead came to us" (Google Places import, Meta Ads, ...).
  It must NOT change once set; reporting funnels rely on it.
- ``source_workflow_id`` is "which workflow OWNS this lead's lifecycle".
  Outreach-imported hotels carry ``outreach_agent_v1`` and stay marked even
  after they reply (Adim 5 webhook will add a separate Etkilesimler row).

After a successful send the runner flips ``asama`` to ``Soguk`` so the same
lead is not picked again. Inbound reply (Adim 5 webhook) overwrites it to
``Sicak``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _build_where(source_workflow_id: str) -> str:
    """NocoDB v2 'where' filter expression."""
    return (
        f"(source_workflow_id,eq,{source_workflow_id})"
        f"~and(asama,eq,Yeni)"
        f"~and(telefon,notblank)"
    )


def pick_next_target(client: Any, leads_table_id: str, source_workflow_id: str) -> dict[str, Any] | None:
    """Return the oldest eligible lead, or None when the queue is empty.

    ``client`` must implement ``list_records(table_id, *, where, limit, sort)``
    (matches ``NocoDBClient`` signature).
    """
    where = _build_where(source_workflow_id)
    response = client.list_records(
        leads_table_id,
        where=where,
        limit=1,
        sort="CreatedAt",  # oldest-first; FIFO
    )
    rows = response.get("list") or []
    return rows[0] if rows else None


def count_sent_today(
    client: Any,
    messages_table_id: str,
    *,
    agent_name: str = "Outreach Agent",
    now: datetime | None = None,
) -> int:
    """Outreach Robotu'nun bugun gonderdigi mesaj sayisi.

    Seyma'nin local script'i bu sayiyi CSV log'undan okuyor; bizim Cloud
    Run worker'i restart edebilir, in-memory sayac sifirlanir. Restart
    sonrasi day_count'i NocoDB Etkilesimler'den geri yukle — boylece
    ayni gun icinde 2x daily_limit ban'i imkansiz.

    Filter: yon=Giden AND agent=<agent_name> AND tarih >= bugun 00:00 UTC.
    UTC sabit; Cloud Run job timezone'undan bagimsiz olur.
    """
    now = now or datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    where = (
        f"(yon,eq,Giden)"
        f"~and(agent,eq,{agent_name})"
        f"~and(tarih,ge,{midnight.isoformat()})"
    )
    response = client.list_records(messages_table_id, where=where, limit=1000)
    return len(response.get("list") or [])


__all__ = ["pick_next_target", "count_sent_today", "_build_where"]
