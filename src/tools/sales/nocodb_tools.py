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
    """Leadler tablosu (Beyza'nin live schema). NOCODB_LEADS_TABLE_ID env'inden okur."""
    return get_settings().nocodb_leads_table_id


def _resolve_messages_table() -> str | None:
    """Etkilesimler tablosu (mesajlar + bildirimler ortak). NOCODB_MESSAGES_TABLE_ID."""
    return get_settings().nocodb_messages_table_id


# notify_seyma artik Etkilesimler'e yaziyor (tur='bildirim'),
# ayri seyma_notifications tablosu kullanilmiyor.


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
    name_override="upsert_lead",
    description_override=(
        "Idempotent upsert: insert OR update by external_id (idempotency key). "
        "Yazdigi tablo: NocoDB 'Leadler' (Beyza'nin n8n workflow'larinin yazdigi tablo). "
        "REQUIRED: external_id, ad_soyad, kaynak, source_workflow_id. "
        "OPTIONAL: leadgen_id (Meta retry guard), telefon, email, sirket_adi, sektor, "
        "konum, web_sitesi, instagram, linkedin_url, google_puani, asama, lead_skoru, "
        "ihtiyac_notu, atanan_kisi, notlar. "
        "Webhook retry'lerinde duplicate uretmez (lookup-then-insert/patch). "
        "kaynak: 'Meta Ads' | 'LinkedIn' | 'Clay' | 'IG DM' | 'TikTok DM' | 'Referans' | 'Manuel'. "
        "asama: 'Yeni' | 'Soguk' | 'Ilik' | 'Sicak' | 'Teklif' | 'Sozlesme' | 'Kazanildi' | 'Kayip' | 'Arsiv'. "
        "lead_skoru: 0-100."
    ),
    strict_mode=False,
)
async def upsert_lead(
    external_id: str,
    ad_soyad: str,
    kaynak: str,
    source_workflow_id: str,
    leadgen_id: str | None = None,
    telefon: str | None = None,
    email: str | None = None,
    sirket_adi: str | None = None,
    sektor: str | None = None,
    konum: str | None = None,
    web_sitesi: str | None = None,
    instagram: str | None = None,
    linkedin_url: str | None = None,
    google_puani: int | None = None,
    asama: str = "Yeni",
    lead_skoru: int = 50,
    ihtiyac_notu: str | None = None,
    atanan_kisi: str | None = None,
    notlar: str | None = None,
) -> dict[str, Any]:
    """Upsert a lead row in 'Leadler' keyed by external_id (idempotency).

    Aligns with Beyza's NocoDB schema (n8n workflows write to the same table).
    See customer_agent/docs/NOCODB-SCHEMA-V2.md for the live contract.
    """
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    fields: dict[str, Any] = {
        "external_id": external_id,
        "ad_soyad": ad_soyad,
        "kaynak": kaynak,
        "source_workflow_id": source_workflow_id,
        "asama": asama,
        "lead_skoru": lead_skoru,
    }
    if leadgen_id:
        fields["leadgen_id"] = leadgen_id
    if telefon:
        fields["telefon"] = telefon
    if email:
        fields["email"] = email
    if sirket_adi:
        fields["sirket_adi"] = sirket_adi
    if sektor:
        fields["sektor"] = sektor
    if konum:
        fields["konum"] = konum
    if web_sitesi:
        fields["web_sitesi"] = web_sitesi
    if instagram:
        fields["instagram"] = instagram
    if linkedin_url:
        fields["linkedin_url"] = linkedin_url
    if google_puani is not None:
        fields["google_puani"] = google_puani
    if ihtiyac_notu:
        fields["ihtiyac_notu"] = ihtiyac_notu
    if atanan_kisi:
        fields["atanan_kisi"] = atanan_kisi
    if notlar:
        fields["notlar"] = notlar

    try:
        result = get_nocodb_client().upsert_record(table_id, "external_id", fields)
        record = result["record"]
        return {
            "success": True,
            "created": result["created"],
            "lead_id": record.get("Id"),
            "record": record,
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="create_lead",
    description_override=(
        "DEPRECATED — use upsert_lead. Plain INSERT without idempotency, kept "
        "only for legacy callers. New code MUST use upsert_lead."
    ),
    strict_mode=False,
)
async def create_lead(
    ad_soyad: str,
    kaynak: str,
    telefon: str | None = None,
    email: str | None = None,
    sirket_adi: str | None = None,
    sektor: str | None = None,
    asama: str = "Yeni",
    lead_skoru: int = 50,
    notlar: str | None = None,
) -> dict[str, Any]:
    """DEPRECATED — Insert a lead row into Leadler. Prefer upsert_lead."""
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    fields: dict[str, Any] = {
        "ad_soyad": ad_soyad,
        "kaynak": kaynak,
        "asama": asama,
        "lead_skoru": lead_skoru,
    }
    if telefon:
        fields["telefon"] = telefon
    if email:
        fields["email"] = email
    if sirket_adi:
        fields["sirket_adi"] = sirket_adi
    if sektor:
        fields["sektor"] = sektor
    if notlar:
        fields["notlar"] = notlar

    try:
        record = get_nocodb_client().create_record(table_id, fields)
        return {"success": True, "lead_id": record.get("Id"), "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="update_lead",
    description_override=(
        "Update an existing lead in Leadler. REQUIRED: lead_id. "
        "Pass any subset of: asama, lead_skoru, ihtiyac_notu, atanan_kisi, notlar, "
        "konum, web_sitesi, instagram, linkedin_url, google_puani."
    ),
    strict_mode=False,
)
async def update_lead(
    lead_id: int,
    asama: str | None = None,
    lead_skoru: int | None = None,
    ihtiyac_notu: str | None = None,
    atanan_kisi: str | None = None,
    notlar: str | None = None,
    konum: str | None = None,
    web_sitesi: str | None = None,
    instagram: str | None = None,
    linkedin_url: str | None = None,
    google_puani: int | None = None,
) -> dict[str, Any]:
    """Patch fields on a Leadler row. Only non-None args are sent."""
    table_id = _resolve_leads_table()
    if not table_id:
        return _missing_table_error("leads")

    fields: dict[str, Any] = {}
    if asama is not None:
        fields["asama"] = asama
    if lead_skoru is not None:
        fields["lead_skoru"] = lead_skoru
    if ihtiyac_notu is not None:
        fields["ihtiyac_notu"] = ihtiyac_notu
    if atanan_kisi is not None:
        fields["atanan_kisi"] = atanan_kisi
    if notlar is not None:
        fields["notlar"] = notlar
    if konum is not None:
        fields["konum"] = konum
    if web_sitesi is not None:
        fields["web_sitesi"] = web_sitesi
    if instagram is not None:
        fields["instagram"] = instagram
    if linkedin_url is not None:
        fields["linkedin_url"] = linkedin_url
    if google_puani is not None:
        fields["google_puani"] = google_puani

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
        "Append a message to Etkilesimler tablosu (Beyza'nin live schema). "
        "REQUIRED: lead_adi (Leadler.ad_soyad ile string match), kanal, yon, mesaj_icerigi. "
        "OPTIONAL: external_message_id (idempotency, ornegin WhatsApp wamid), tur, sonuc, agent, notlar. "
        "kanal: 'LinkedIn' | 'Email' | 'WhatsApp' | 'IG DM' | 'TikTok DM' | 'Telefon' | 'Meta Form' | 'Yuz Yuze'. "
        "yon: 'Giden' | 'Gelen'. "
        "tur: 'Baglanti Istegi' | 'Ilk Mesaj' | 'Takip Mesaji' | 'Itiraz Karsilama' | 'Discovery Call' | 'Teklif' | 'Yanit'. "
        "sonuc: 'Yanit Bekleniyor' | 'Olumlu Yanit' | 'Olumsuz Yanit' | 'Itiraz' | 'Soru Sordu' | 'Gorusme Planlandi'. "
        "agent: 'LinkedIn Agent' | 'Meta Agent' | 'Clay Agent' | 'DM Bot' | 'Takip Agent' | 'Itiraz Agent' | 'Seyma'."
    ),
    strict_mode=False,
)
async def log_lead_message(
    lead_adi: str,
    kanal: str,
    yon: str,
    mesaj_icerigi: str,
    external_message_id: str | None = None,
    tur: str | None = None,
    sonuc: str | None = None,
    agent: str | None = None,
    notlar: str | None = None,
    otomatik_mi: bool = True,
) -> dict[str, Any]:
    """Append a row to Etkilesimler. Aligns with Beyza's n8n workflow schema."""
    table_id = _resolve_messages_table()
    if not table_id:
        return _missing_table_error("lead_messages")

    fields: dict[str, Any] = {
        "lead_adi": lead_adi,
        "tarih": datetime.utcnow().isoformat(),
        "kanal": kanal,
        "yon": yon,
        "mesaj_icerigi": mesaj_icerigi,
        "otomatik_mi": otomatik_mi,
    }
    if external_message_id:
        fields["external_message_id"] = external_message_id
    if tur:
        fields["tur"] = tur
    if sonuc:
        fields["sonuc"] = sonuc
    if agent:
        fields["agent"] = agent
    if notlar:
        fields["notlar"] = notlar

    try:
        # Idempotency: external_message_id varsa upsert, yoksa duz insert
        client = get_nocodb_client()
        if external_message_id:
            result = client.upsert_record(table_id, "external_message_id", fields)
            record = result["record"]
            return {
                "success": True,
                "created": result["created"],
                "message_id": record.get("Id"),
                "record": record,
            }
        record = client.create_record(table_id, fields)
        return {"success": True, "message_id": record.get("Id"), "record": record}
    except Exception as exc:
        return classify_error(exc, "nocodb")


@function_tool(
    name_override="notify_seyma",
    description_override=(
        "Flag a lead for Seyma's attention. Implementation: Leadler.atanan_kisi='Seyma' "
        "+ notlar'a timestamp'li bildirim notu append edilir; tetikleyici='sicak_lead' "
        "ise asama='Sicak' yapilir. Beyza'nin n8n 'Send Hot Lead Alert (Gmail)' "
        "workflow'u Seyma'ya zaten Gmail ile alert atiyor — bu tool CRM uzerinde "
        "kalici audit trail birakir, kanal cakismasi olmaz. "
        "REQUIRED: lead_id, tetikleyici. "
        "tetikleyici: 'sicak_lead' | '2_itiraz' | 'teklif_zamani' | 'manuel'."
    ),
    strict_mode=False,
)
async def notify_seyma(
    lead_id: int,
    tetikleyici: str,
    not_metni: str | None = None,
) -> dict[str, Any]:
    """Flag lead for Seyma — updates Leadler row (atanan_kisi + notlar + asama)."""
    leads_table = _resolve_leads_table()
    if not leads_table:
        return _missing_table_error("leads")

    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    note_line = f"[{timestamp}] Seyma'ya yonlendirildi (tetikleyici={tetikleyici})"
    if not_metni:
        note_line += f": {not_metni}"

    try:
        client = get_nocodb_client()
        existing = client.get_record(leads_table, lead_id)
        old_notlar = existing.get("notlar") if isinstance(existing, dict) else None
        new_notlar = (
            f"{old_notlar}\n{note_line}".strip() if old_notlar else note_line
        )

        update_fields: dict[str, Any] = {
            "atanan_kisi": "Seyma",
            "notlar": new_notlar,
        }
        if tetikleyici == "sicak_lead":
            update_fields["asama"] = "Sicak"

        record = client.update_record(leads_table, lead_id, update_fields)
        return {
            "success": True,
            "lead_id": lead_id,
            "atanan_kisi": "Seyma",
            "record": record,
        }
    except Exception as exc:
        return classify_error(exc, "nocodb")


# ---------------------------------------------------------------------------
# Tool group
# ---------------------------------------------------------------------------


def get_nocodb_tools() -> list:
    """All NocoDB tools sales agentlari icin tek listede."""
    return [
        upsert_lead,
        update_lead,
        get_lead,
        query_leads,
        log_lead_message,
        notify_seyma,
    ]


__all__ = [
    "upsert_lead",
    "create_lead",  # deprecated, kept for legacy callers
    "update_lead",
    "get_lead",
    "query_leads",
    "log_lead_message",
    "notify_seyma",
    "get_nocodb_tools",
]
