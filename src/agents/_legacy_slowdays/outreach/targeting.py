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

Pick strategy (sessiz ucluyu canlandirma — outreach motoru):
- En eski leadi koru, ama kor FIFO degil: NocoDB'den oldest-first N lead
  cek (default 25), ``score_lead`` ile puanla, en yuksek skorlu olani sec.
  Esit puan -> ilk siradaki (eski FIFO). Boylece otel adi belli, hedef
  bolgede, TR numarali leadler oncelik kazanir. Gonderim ritmi/template/
  ban-koruma mantigina dokunulmadi.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_TARGET_REGIONS = {
    "mugla", "muğla",
    "antalya",
    "aydin", "aydın",
    "izmir", "i̇zmir", "İzmir",
}

# Aday havuz boyutu — burdan en iyisi secilir. Cok kucuk havuz akilsizlasir,
# cok buyuk havuz NocoDB'ye yuk biner. 25 makul.
_CANDIDATE_POOL_SIZE = 25


def _build_where(source_workflow_id: str) -> str:
    """NocoDB v2 'where' filter expression."""
    return (
        f"(source_workflow_id,eq,{source_workflow_id})"
        f"~and(asama,eq,Yeni)"
        f"~and(telefon,notblank)"
    )


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def score_lead(lead: dict[str, Any]) -> int:
    """Lead kalite skoru. Yuksek = once mesaj at.

    Kurallar:
    - Otel/sirket adi var: +3 (gercek isletme, isim ile selamlanabilir)
    - Turkiye numarasi (+90): +2
    - Hedef bolgede (Mugla/Antalya/Aydin/Izmir): +2
    - Kisi adi var: +1
    """
    score = 0
    if _norm(lead.get("sirket_adi")):
        score += 3
    phone = _norm(lead.get("telefon"))
    if phone.startswith("+90") or phone.startswith("90"):
        score += 2
    region = _norm(lead.get("il")) or _norm(lead.get("sehir"))
    if region and region in _TARGET_REGIONS:
        score += 2
    if _norm(lead.get("ad_soyad")):
        score += 1
    return score


def pick_next_target(
    client: Any,
    leads_table_id: str,
    source_workflow_id: str,
    *,
    candidate_pool: int = _CANDIDATE_POOL_SIZE,
) -> dict[str, Any] | None:
    """Return the highest-scoring eligible lead, or None when the queue is empty.

    Stable: equal scores fall back to oldest-first (FIFO) — NocoDB sort
    guarantees that. ``client`` must implement
    ``list_records(table_id, *, where, limit, sort)``.
    """
    where = _build_where(source_workflow_id)
    response = client.list_records(
        leads_table_id,
        where=where,
        limit=candidate_pool,
        sort="CreatedAt",  # oldest-first; tie-breaker FIFO
    )
    rows = response.get("list") or []
    if not rows:
        return None

    best = rows[0]
    best_score = score_lead(best)
    for row in rows[1:]:
        s = score_lead(row)
        if s > best_score:
            best = row
            best_score = s
    return best


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
    "pick_next_target",
    "score_lead",
    "count_sent_today",
    "_build_where",
]
