"""Compute 24h health metrics from NocoDB Etkilesimler."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class GuardianMetrics:
    """Pencere icindeki ham sayilar + turetilmis oranlar."""

    window_hours: int
    outreach_sent: int
    inbound_received: int
    auto_replies_sent: int
    outreach_failed: int

    @property
    def reply_rate_pct(self) -> float:
        return (
            round(100 * self.inbound_received / self.outreach_sent, 2)
            if self.outreach_sent
            else 0.0
        )

    @property
    def engagement_rate_pct(self) -> float:
        return (
            round(100 * self.auto_replies_sent / self.inbound_received, 2)
            if self.inbound_received
            else 0.0
        )

    @property
    def failure_rate_pct(self) -> float:
        total = self.outreach_sent + self.outreach_failed
        return (
            round(100 * self.outreach_failed / total, 2)
            if total
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_hours": self.window_hours,
            "outreach_sent": self.outreach_sent,
            "inbound_received": self.inbound_received,
            "auto_replies_sent": self.auto_replies_sent,
            "outreach_failed": self.outreach_failed,
            "reply_rate_pct": self.reply_rate_pct,
            "engagement_rate_pct": self.engagement_rate_pct,
            "failure_rate_pct": self.failure_rate_pct,
        }


def _count_where(client: Any, table_id: str, where: str) -> int:
    """List + count helper. Pages up to 1000 — yeterli (24h, kucuk Slowdays)."""
    response = client.list_records(table_id, where=where, limit=1000)
    return len(response.get("list") or [])


def compute_metrics(
    client: Any,
    messages_table_id: str,
    *,
    window_hours: int = 24,
    now: datetime | None = None,
) -> GuardianMetrics:
    """Pull 24h counts from Etkilesimler. Pure NocoDB read — no decisions."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(hours=window_hours)).isoformat()

    outreach_sent = _count_where(
        client,
        messages_table_id,
        where=(
            f"(yon,eq,Giden)~and(agent,eq,Outreach Agent)"
            f"~and(tarih,ge,{since})"
        ),
    )
    inbound_received = _count_where(
        client,
        messages_table_id,
        where=f"(yon,eq,Gelen)~and(tarih,ge,{since})",
    )
    auto_replies_sent = _count_where(
        client,
        messages_table_id,
        where=(
            f"(yon,eq,Giden)~and(agent,eq,Auto-reply Agent)"
            f"~and(tarih,ge,{since})"
        ),
    )
    # FAILED log Adim 9'da Outreach runner'a eklenecek (status field).
    # Simdilik 0 — Outreach exception'lar in-memory log'a duser, NocoDB'ye
    # yazilmiyor. Bu metrik aktif olunca filter:
    #   (yon,eq,Giden)~and(agent,eq,Outreach Agent)~and(status,eq,FAILED)
    outreach_failed = 0

    return GuardianMetrics(
        window_hours=window_hours,
        outreach_sent=outreach_sent,
        inbound_received=inbound_received,
        auto_replies_sent=auto_replies_sent,
        outreach_failed=outreach_failed,
    )
