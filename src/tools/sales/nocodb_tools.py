"""NocoDB CRM tools for sales agents (Meta, LinkedIn, Clay, IG DM, Takip, Itiraz).

All tools return structured dicts so agents can react to errors via
``error_code`` / ``retryable`` / ``user_message_tr`` fields (errors.py pattern).

Tablolar (env'den table id okunur):
- leads             -> NOCODB_LEADS_TABLE_ID
- lead_messages     -> NOCODB_MESSAGES_TABLE_ID
- seyma_notifications -> NOCODB_NOTIFICATIONS_TABLE_ID
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from agents import function_tool

from src.app.config import get_settings
from src.infra.errors import classify_error
from src.infra.nocodb_client import get_nocodb_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_leads_table() -> str | None:
    return get_settings().nocodb_leads_table_id


def _resolve_messages_table() -> str | None:
    return get_settings().nocodb_messages_table_id


def _resolve_notifications_table() -> str | None:
    return get_settings().nocodb_notifications_table_id


def _missing_table_error(name: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": f"NocoDB {name} table id is not configured (env).",
        "error_code": "INVALID_INPUT",
        "service": "nocodb",
        "retryable": False,
        "user_message_tr": "CRM tablo ayarlari eksik, yonetici bilgilendirildi.",
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@function_tool(
    name_override="create_lead",
    description_override=(
        "Create a new lead in NocoDB CRM (leads tablosu). "
        "REQUIRED: isim. RECOMMENDED: telefon, email, sirket, sektor, kaynak, asama, skor, not. "
        "kaynak: 'Meta' | 'LinkedIn' | 'Clay' | 'IG DM' | 'Referans'. "
        "asama: 'Yeni' | 'Soguk' | 'Ilik' | 'Sicak' | 'Teklif' | 'Kazanildi' | 'Kayip'. "
        "skor: 0-100 lead score (yuksek = sicak)."
    ),
    strict_mode=False,
)
async def create_lead(
    isim: str,
    kaynak: str,
    telefon: str | None = None,
    email: str | None = None,
    sirket: str | None = None,
    sektor: str | None = None,
    asama: str = "Yeni",
    skor: int = 50,
    not_metni: str | None = None,
) -> dict[str, Any]:
    """Insert a lead row into NocoDB."""
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    fields: dict[str, Any] = {
        "isim": isim,
        "kaynak": kaynak,
        "asama": asama,
        "skor": skor,
        "takip_sayisi": 0,
        "seyma_bildirildi": False,
    }
    if telefon:
        fields["telefon"] = telefon
    if email:
        fields["email"] = email
    if sirket:
        fields["sirket"] = sirket
    if sektor:
        fields["sektor"] = sektor
    if not_metni:
        fields["not"] = not_metni

    try:
        record = get_nocodb_client().create_record(table_id, fields)
        return {"success": True, "lead_id": record.get("Id"), "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="update_lead",
    description_override=(
        "Update an existing lead. REQUIRED: lead_id. "
        "Pass any subset of: asama, skor, son_iletisim, takip_sayisi, seyma_bildirildi, not_metni."
    ),
    strict_mode=False,
)
async def update_lead(
    lead_id: int,
    asama: str | None = None,
    skor: int | None = None,
    son_iletisim: str | None = None,
    takip_sayisi: int | None = None,
    seyma_bildirildi: bool | None = None,
    not_metni: str | None = None,
) -> dict[str, Any]:
    """Patch fields on a lead row. Only non-None args are sent."""
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    fields: dict[str, Any] = {}
    if asama is not None:
        fields["asama"] = asama
    if skor is not None:
        fields["skor"] = skor
    if son_iletisim is not None:
        fields["son_iletisim"] = son_iletisim
    if takip_sayisi is not None:
        fields["takip_sayisi"] = takip_sayisi
    if seyma_bildirildi is not None:
        fields["seyma_bildirildi"] = seyma_bildirildi
    if not_metni is not None:
        fields["not"] = not_metni

    if not fields:
        return {"success": False, "error": "No fields to update."}

    try:
        record = get_nocodb_client().update_record(table_id, lead_id, fields)
        return {"success": True, "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="get_lead",
    description_override="Fetch a single lead by id from NocoDB.",
    strict_mode=False,
)
async def get_lead(lead_id: int) -> dict[str, Any]:
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    try:
        record = get_nocodb_client().get_record(table_id, lead_id)
        return {"success": True, "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="query_leads",
    description_override=(
        "List leads with an optional NocoDB where filter. "
        "where syntax: '(field,op,value)' where op is eq|neq|gt|lt|like (e.g. '(asama,eq,Sicak)'). "
        "Multiple filters: '(asama,eq,Sicak)~and(kaynak,eq,Meta)'. "
        "limit defaults to 25, max 100."
    ),
    strict_mode=False,
)
async def query_leads(
    where: str | None = None,
    limit: int = 25,
    sort: str | None = None,
) -> dict[str, Any]:
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    try:
        result = get_nocodb_client().list_records(
            table_id, where=where, limit=min(limit, 100), sort=sort
        )
        records = result.get("list", []) if isinstance(result, dict) else []
        return {"success": True, "results": records, "count": len(records)}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="log_lead_message",
    description_override=(
        "Append a message to lead_messages tablosu. "
        "REQUIRED: lead_id, kanal, yon, mesaj. "
        "kanal: 'LinkedIn' | 'IG' | 'WhatsApp' | 'Email' | 'Meta'. "
        "yon: 'giden' | 'gelen'."
    ),
    strict_mode=False,
)
async def log_lead_message(
    lead_id: int,
    kanal: str,
    yon: str,
    mesaj: str,
) -> dict[str, Any]:
    table_id = _resolve_messages_table()
    if not table_id:
        return _missing_table_error("lead_messages")

    fields = {
        "lead_id": lead_id,
        "kanal": kanal,
        "yon": yon,
        "mesaj": mesaj,
    }
    try:
        record = get_nocodb_client().create_record(table_id, fields)
        return {"success": True, "message_id": record.get("Id"), "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="notify_seyma",
    description_override=(
        "Push a Seyma notification (seyma_notifications tablosu). "
        "REQUIRED: lead_id, tetikleyici. "
        "tetikleyici: 'sicak_lead' | '2_itiraz' | 'teklif_zamani' | 'manuel'. "
        "Side-effect: also marks the lead as seyma_bildirildi=True if tetikleyici='sicak_lead'."
    ),
    strict_mode=False,
)
async def notify_seyma(
    lead_id: int,
    tetikleyici: str,
    not_metni: str | None = None,
) -> dict[str, Any]:
    table_id = _resolve_notifications_table()
    if not table_id:
        return _missing_table_error("seyma_notifications")

    fields: dict[str, Any] = {
        "lead_id": lead_id,
        "tetikleyici": tetikleyici,
        "durum": "bekliyor",
    }
    if not_metni:
        fields["not"] = not_metni

    try:
        client = get_nocodb_client()
        record = client.create_record(table_id, fields)

        # Sicak lead ise leads tablosunda da bayragi kaldir
        if tetikleyici == "sicak_lead":
            leads_table = _resolve_leads_table()
            if leads_table:
                client.update_record(
                    leads_table,
                    lead_id,
                    {
                        "seyma_bildirildi": True,
                        "asama": "Sicak",
                        "son_iletisim": datetime.utcnow().isoformat(),
                    },
                )

        return {"success": True, "notification_id": record.get("Id"), "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Tool group
# ---------------------------------------------------------------------------


def get_nocodb_tools() -> list:
    """All NocoDB tools sales agentlari icin tek listede."""
    return [
        create_lead,
        update_lead,
        get_lead,
        query_leads,
        log_lead_message,
        notify_seyma,
    ]


__all__ = [
    "create_lead",
    "update_lead",
    "get_lead",
    "query_leads",
    "log_lead_message",
    "notify_seyma",
    "get_nocodb_tools",
]
