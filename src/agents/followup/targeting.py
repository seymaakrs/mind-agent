"""NocoDB target picker for Follow-up Agent.

Aday lead:
    source_workflow_id  = X (outreach ile ayni leadler)
    asama               = 'Soguk'  (outreach gonderildi, henuz cevap yok)
    son_temas           <  bugun - N gun  (yeterince zaman gecmis)

Python filtresi:
    notlar     'Takip gonderildi' ICERMIYOR  (idempotency — ayni leade ikinci
                                              kez takip atmamak icin)

Not: asama=Soguk filtresi cevap gelen leadleri dogal olarak elemeli; cunku
auto_reply Gelen mesaj icin asama'yi 'Takipte'/'Itiraz'/'Sicak'a cevirir.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


_FOLLOWUP_MARKER = "Takip gonderildi"
_CANDIDATE_POOL_SIZE = 25


def _build_where(source_workflow_id: str, cutoff: datetime) -> str:
    """NocoDB v2 'where': source + asama=Soguk + son_temas < cutoff_date.

    NocoDB v2 datetime sadece exactDate kabul ediyor; cutoff date string'e
    cevrilir, gun bazinda kaba pencere yeterli (jitter zaten var).
    """
    cutoff_date = cutoff.astimezone(timezone.utc).date().isoformat()
    return (
        f"(source_workflow_id,eq,{source_workflow_id})"
        f"~and(asama,eq,Soguk)"
        f"~and(son_temas,lt,exactDate,{cutoff_date})"
    )


def _already_followed_up(lead: dict[str, Any]) -> bool:
    return _FOLLOWUP_MARKER in (lead.get("notlar") or "")


def find_followup_targets(
    client: Any,
    leads_table_id: str,
    source_workflow_id: str,
    *,
    days_since_outreach: int = 3,
    candidate_pool: int = _CANDIDATE_POOL_SIZE,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Cevapsiz soguk leadleri (takip atilmamis olanlar) en eskiden yeniye dondur.

    Empty list = aday yok / hata. NocoDB hatasinda defansif (bos liste).
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_since_outreach)
    where = _build_where(source_workflow_id, cutoff)
    try:
        response = client.list_records(
            leads_table_id,
            where=where,
            limit=candidate_pool,
            sort="son_temas",  # en eski temas ilk — once en cok bekleyenler
        )
    except Exception:
        return []
    rows = response.get("list") or []
    return [r for r in rows if not _already_followed_up(r)]


def count_sent_today(
    client: Any,
    messages_table_id: str,
    *,
    agent_name: str = "Followup Agent",
    now: datetime | None = None,
) -> int:
    """Follow-up'in bugun gonderdigi mesaj sayisi (restart-safe sayac)."""
    from src.infra.nocodb_client import today_filter_clause
    now = now or datetime.now(timezone.utc)
    where = (
        f"(yon,eq,Giden)"
        f"~and(agent,eq,{agent_name})"
        f"~and{today_filter_clause('tarih', now)}"
    )
    response = client.list_records(messages_table_id, where=where, limit=1000)
    return len(response.get("list") or [])


__all__ = [
    "find_followup_targets",
    "count_sent_today",
    "_build_where",
    "_already_followed_up",
    "_FOLLOWUP_MARKER",
]
