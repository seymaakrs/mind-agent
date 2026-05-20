"""NocoDB queries for Auto-reply Agent.

Picks Etkilesimler rows where:
    yon                   = 'Gelen'
    auto_reply_processed  = false
    tarih                 > now - max_inbound_age_minutes

Oldest first (FIFO). Worker iterates the batch.

Ayrica: ``fetch_recent_history`` lead bazli son N mesaji (Gelen+Giden)
kronolojik dondurur — auto_reply'in hafiza yetenegi icin (responder bunu
LLM prompt'una anchor olarak verir).
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
    """Return a batch of unprocessed inbound messages, oldest first."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    where = _build_where(now=now)
    response = client.list_records(
        messages_table_id,
        where=where,
        limit=max(batch_size * 4, 50),
        sort="tarih",
    )
    rows = response.get("list") or []
    fresh = []
    for r in rows:
        ts = r.get("tarih")
        if not ts:
            continue
        try:
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


def _safe_name(lead_adi: str) -> str:
    """NocoDB v2 'where' icinde virgul ayraci; lead_adi virgul tasiyorsa
    bosluga cevir (defansif, eq ile birebir eslesme korunmali)."""
    return (lead_adi or "").replace(",", " ").strip()


def fetch_recent_history(
    client: Any,
    messages_table_id: str,
    lead_adi: str,
    *,
    limit: int = 10,
    exclude_row_id: int | None = None,
) -> list[dict[str, Any]]:
    """Bir lead icin son N mesaji (Gelen+Giden) kronolojik dondur.

    Filtre: lead_adi=X. Sort: -tarih (en yeni once), Python'da reverse edilir
    -> en eski once. ``exclude_row_id`` verildiyse o satir liste disinda kalir
    (ornek: auto_reply suanki gelen mesaji history'de tekrar gormesin).

    NocoDB hata verirse bos liste doner (defansif — hafiza opsiyoneldir).
    """
    name = _safe_name(lead_adi)
    if not name:
        return []
    try:
        response = client.list_records(
            messages_table_id,
            where=f"(lead_adi,eq,{name})",
            limit=max(limit + 1, 1),  # exclude varsa 1 fazla cek
            sort="-tarih",
        )
    except Exception:
        return []
    rows = response.get("list") or []
    filtered = [
        r for r in rows
        if exclude_row_id is None or r.get("Id") != exclude_row_id
    ][:limit]
    # Kronolojik: en eski once
    return list(reversed(filtered))


__all__ = ["find_pending_inbounds", "fetch_recent_history", "_build_where"]
