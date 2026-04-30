"""NocoDB CRUD tools exposed to sales sub-agents (Clay, IG DM, LinkedIn, Meta).

These wrap ``NocoDBClient`` with the OpenAI Agents SDK ``@function_tool``
decorator. They catch errors and return structured dicts so the LLM can read
the outcome.

Whitelist (write-allowed) tables for sales agents:
- leads
- lead_messages
- seyma_notifications
- decisions_log

Read-only via ``query_records`` /  ``get_record``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents import function_tool

from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client


# ---------------------------------------------------------------------------
# Lead CRUD
# ---------------------------------------------------------------------------


@function_tool
async def create_lead(
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    company: str | None = None,
    sector: str | None = None,
    location: str | None = None,
    lead_score: int = 0,
    lead_status: str = "cold",
    source: str = "manual",
    consent_status: bool = False,
    consent_source: str | None = None,
    zernio_thread_id: str | None = None,
    zernio_account_id: str | None = None,
    assigned_to: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Yeni bir lead'i NocoDB CRM'e kaydeder.

    Args:
        name: Lead'in adı.
        email: E-posta.
        phone: Telefon (uluslararası format önerilir).
        company: İşletme adı.
        sector: Sektör (otel, restoran, cafe, e-ticaret, ...).
        location: Şehir / bölge ("Bodrum", "Muğla").
        lead_score: 0-10 arası skor (Zernio spec'i: web yok+IG zayıf=10).
        lead_status: cold / warm / hot / closed / lost.
        source: meta / clay / linkedin / ig_dm / manual / referral.
        consent_status: KVKK onayı verildi mi.
        consent_source: Onay kaynağı ("form_v1", "linkedin_message", ...).
        zernio_thread_id: Zernio Inbox thread referansı (varsa).
        zernio_account_id: Zernio'da hangi sosyal hesap.
        assigned_to: Hangi agent ilgileniyor.
        tags: Serbest etiketler.
        notes: Serbest not.

    Returns:
        ``{"success": True, "lead_id": int, "data": dict}`` veya
        ``{"success": False, "error_code": str, "error": str}``.
    """
    try:
        client = get_nocodb_client()
        fields: dict[str, Any] = {
            "lead_score": max(0, min(10, lead_score)),
            "lead_status": lead_status,
            "source": source,
            "consent_status": consent_status,
        }
        # Optional fields — only include when provided to avoid overwriting
        # existing data on update endpoints that share this serializer.
        for key, val in {
            "name": name,
            "email": email,
            "phone": phone,
            "company": company,
            "sector": sector,
            "location": location,
            "consent_source": consent_source,
            "zernio_thread_id": zernio_thread_id,
            "zernio_account_id": zernio_account_id,
            "assigned_to": assigned_to,
            "notes": notes,
        }.items():
            if val is not None:
                fields[key] = val
        if consent_status:
            fields["consent_recorded_at"] = datetime.now(timezone.utc).isoformat()
        if tags:
            fields["tags"] = ",".join(tags)  # NocoDB MultiSelect accepts comma-separated
        fields["first_contact_at"] = datetime.now(timezone.utc).isoformat()
        fields["last_action_at"] = fields["first_contact_at"]

        record = await client.create_record(client.config.leads_table_id, fields)
        return {
            "success": True,
            "lead_id": record.get("Id"),
            "data": record,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def update_lead(
    lead_id: int,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    lead_score: int | None = None,
    lead_status: str | None = None,
    consent_status: bool | None = None,
    assigned_to: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Mevcut lead'i günceller.

    Args:
        lead_id: NocoDB Id.
        Diğer parametreler: yalnızca verilen alanlar güncellenir.
    """
    try:
        client = get_nocodb_client()
        fields: dict[str, Any] = {"last_action_at": datetime.now(timezone.utc).isoformat()}
        for key, val in {
            "name": name,
            "email": email,
            "phone": phone,
            "lead_score": lead_score,
            "lead_status": lead_status,
            "consent_status": consent_status,
            "assigned_to": assigned_to,
            "notes": notes,
        }.items():
            if val is not None:
                fields[key] = val

        record = await client.update_record(client.config.leads_table_id, lead_id, fields)
        return {"success": True, "data": record}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def get_lead(lead_id: int) -> dict[str, Any]:
    """Tek bir lead'i Id ile çeker.

    Args:
        lead_id: NocoDB Id.
    """
    try:
        client = get_nocodb_client()
        record = await client.get_record(client.config.leads_table_id, lead_id)
        return {"success": True, "data": record}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


@function_tool
async def query_leads(
    where: str | None = None,
    sort: str | None = "-CreatedAt",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Lead'leri filtre + sıralama + sayfalama ile sorgular.

    NocoDB filter syntax: ``(field,op,value)``. Örnekler:
        - ``(lead_score,gte,8)`` — sıcak lead'ler
        - ``(lead_status,eq,hot)`` — durum
        - ``(source,eq,clay)~and(lead_score,gte,5)`` — ve birleşimi

    Args:
        where: NocoDB filter expression.
        sort: Sıralama, ``-CreatedAt`` (en yeni önce).
        limit: 1-1000 arası.
        offset: Sayfalama offset.
    """
    try:
        client = get_nocodb_client()
        rows = await client.query_records(
            client.config.leads_table_id,
            where=where,
            sort=sort,
            limit=max(1, min(1000, limit)),
            offset=max(0, offset),
        )
        return {"success": True, "count": len(rows), "data": rows}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Lead Messages
# ---------------------------------------------------------------------------


@function_tool
async def log_lead_message(
    lead_id: int,
    body: str,
    direction: str = "outbound",
    channel: str | None = None,
    agent_name: str | None = None,
    is_auto_generated: bool = True,
    cbo_compliant: bool = True,
    zernio_message_id: str | None = None,
) -> dict[str, Any]:
    """Lead ile yapılan mesajlaşmayı kaydeder.

    Args:
        lead_id: Linked lead Id.
        body: Mesaj metni.
        direction: ``inbound`` / ``outbound``.
        channel: ``meta_dm`` / ``instagram_dm`` / ``linkedin_dm`` / ``email`` /
                 ``whatsapp`` / ``phone`` / ``internal_note``.
        agent_name: Mesajı üreten agent.
        is_auto_generated: LLM mi üretti.
        cbo_compliant: CBO yasakli ifade kontrolü geçti mi.
        zernio_message_id: Zernio mesaj id (idempotency).
    """
    try:
        client = get_nocodb_client()
        fields: dict[str, Any] = {
            "lead_id": lead_id,
            "body": body,
            "direction": direction,
            "is_auto_generated": is_auto_generated,
            "cbo_compliant": cbo_compliant,
        }
        if channel:
            fields["channel"] = channel
        if agent_name:
            fields["agent_name"] = agent_name
        if zernio_message_id:
            fields["zernio_message_id"] = zernio_message_id
        record = await client.create_record(client.config.messages_table_id, fields)
        return {"success": True, "message_id": record.get("Id"), "data": record}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


# ---------------------------------------------------------------------------
# Şeyma Notifications
# ---------------------------------------------------------------------------


@function_tool
async def notify_seyma(
    lead_id: int,
    summary: str,
    lead_score: int = 0,
    suggested_next_action: str | None = None,
    urgency: str = "normal",
) -> dict[str, Any]:
    """Şeyma'ya yeni bir bildirim oluşturur (sıcak lead, müdahale gerektiren durum).

    Args:
        lead_id: İlgili lead Id.
        summary: Kısa özet.
        lead_score: 0-10.
        suggested_next_action: Tavsiye edilen sonraki adım.
        urgency: ``normal`` / ``high`` / ``urgent``.
    """
    try:
        client = get_nocodb_client()
        fields = {
            "lead_id": lead_id,
            "summary": summary,
            "lead_score": lead_score,
            "urgency": urgency,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if suggested_next_action:
            fields["suggested_next_action"] = suggested_next_action
        record = await client.create_record(
            client.config.notifications_table_id, fields
        )
        return {"success": True, "notification_id": record.get("Id"), "data": record}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "nocodb")}


__all__ = [
    "create_lead",
    "update_lead",
    "get_lead",
    "query_leads",
    "log_lead_message",
    "notify_seyma",
]
