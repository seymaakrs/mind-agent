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


__all__ = ["pick_next_target", "_build_where"]
