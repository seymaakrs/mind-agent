"""
customer_agent tool'lari — mind-agent'in customer_agent ekosistemi
(NocoDB) ile konusmasi icin orchestrator/sub-agent katmanindan kullanilir.

Tasarim:
- Her tool baslangicta capability flag kontrolu yapar (defense in depth):
  flag kapali ise NocoDB'ye HIC erisilmez, FEATURE_DISABLED doner.
- NocoDBClient lazy olarak Settings'den olusturulur — Settings eksikse,
  flag acik olsa bile FEATURE_DISABLED'a benzer 'config_missing' doner.
- Tool sonuclari LLM-dostu sade dict'tir; NocoDB schema detayi sizmaz.

Sozlesme: docs/customer-integration-contract.md
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from agents import FunctionTool, function_tool

from src.app.config import get_customer_agent_flags, get_settings
from src.infra.nocodb_client import NocoDBClient, NocoDBConfig


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _feature_disabled(capability: str) -> dict[str, Any]:
    """Kapasite kapali — kullaniciya gosterilebilecek nazik hata."""
    return {
        "success": False,
        "error_code": "FEATURE_DISABLED",
        "error": f"Customer agent capability '{capability}' is disabled.",
        "retryable": False,
        "user_message_tr": (
            "Bu ozellik su an kapali. Yonetici Firebase'den ilgili bayragi "
            "acmadan kullanilamaz."
        ),
    }


def _config_missing(missing: list[str]) -> dict[str, Any]:
    """NocoDB env eksik — kullaniciya teknik hata."""
    return {
        "success": False,
        "error_code": "CONFIG_MISSING",
        "error": f"NocoDB config missing env vars: {missing}",
        "retryable": False,
        "user_message_tr": (
            "CRM baglantisi konfigure edilmemis. Yonetici .env dosyasini kontrol etmeli."
        ),
    }


def _build_nocodb_client() -> NocoDBClient | dict[str, Any]:
    """
    Settings'den NocoDBClient olusturur. Eksik konfig durumunda dict (hata) doner.

    Lazy init: customer_tools modulu import edildiginde Settings yuklenmez —
    sadece capability acik olan ve kullanilan bir tool calistiginda olur.
    """
    settings = get_settings()
    try:
        config = NocoDBConfig.from_settings(
            base_url=settings.nocodb_base_url,
            api_token=settings.nocodb_api_token,
            base_id=settings.nocodb_base_id,
            table_leads=settings.nocodb_table_leads,
            table_pipeline=settings.nocodb_table_pipeline,
            table_etkilesimler=settings.nocodb_table_etkilesimler,
        )
    except ValueError as exc:
        return _config_missing([str(exc)])
    return NocoDBClient(config)


def _summarize_lead(record: dict[str, Any]) -> dict[str, Any]:
    """NocoDB ham kaydini LLM-dostu sade dict'e cevirir (tolerant reader)."""
    return {
        "Id": record.get("Id"),
        "ad_soyad": record.get("ad_soyad"),
        "sirket_adi": record.get("sirket_adi"),
        "asama": record.get("asama"),
        "lead_skoru": record.get("lead_skoru"),
        "kaynak": record.get("kaynak"),
        "sektor": record.get("sektor"),
        "konum": record.get("konum"),
        "web_sitesi": record.get("web_sitesi"),
        "olusturma_tarihi": record.get("olusturma_tarihi"),
    }


# ---------------------------------------------------------------------------
# Tool implementations (test-edilebilir saf async fonksiyonlar)
# ---------------------------------------------------------------------------


async def _customer_search_leads_impl(
    asama: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    flags = get_customer_agent_flags()
    if not flags.is_capability_enabled("can_read_leads"):
        return _feature_disabled("can_read_leads")

    client_or_err = _build_nocodb_client()
    if isinstance(client_or_err, dict):
        return client_or_err
    client = client_or_err

    where = f"(asama,eq,{asama})" if asama else None
    safe_limit = max(1, min(limit, 50))  # 1..50 arasi sabitle

    result = await client.list_leads(where=where, limit=safe_limit)
    if not result["success"]:
        return result

    records = result.get("records", [])
    return {
        "success": True,
        "count": len(records),
        "leads": [_summarize_lead(r) for r in records],
        "page_info": result.get("page_info", {}),
    }


async def _customer_get_lead_impl(lead_id: int | str) -> dict[str, Any]:
    flags = get_customer_agent_flags()
    if not flags.is_capability_enabled("can_read_leads"):
        return _feature_disabled("can_read_leads")

    client_or_err = _build_nocodb_client()
    if isinstance(client_or_err, dict):
        return client_or_err
    client = client_or_err

    result = await client.get_lead(lead_id)
    if not result["success"]:
        return result

    return {"success": True, "lead": _summarize_lead(result["record"])}


async def _customer_get_pipeline_summary_impl() -> dict[str, Any]:
    flags = get_customer_agent_flags()
    if not flags.is_capability_enabled("can_read_pipeline"):
        return _feature_disabled("can_read_pipeline")

    client_or_err = _build_nocodb_client()
    if isinstance(client_or_err, dict):
        return client_or_err
    client = client_or_err

    result = await client.list_pipeline(limit=100)
    if not result["success"]:
        return result

    records = result.get("records", [])
    by_stage = Counter(r.get("asama", "Bilinmeyen") for r in records)
    won = [r for r in records if r.get("asama") == "Kazanildi"]
    total_revenue = sum(int(r.get("tutar") or 0) for r in won)

    return {
        "success": True,
        "total_records": len(records),
        "by_stage": dict(by_stage),
        "won_count": len(won),
        "won_revenue_total_try": total_revenue,
    }


# ---------------------------------------------------------------------------
# Function tools (LLM tarafindan cagirilir)
# ---------------------------------------------------------------------------


@function_tool(
    name_override="customer_search_leads",
    description_override=(
        "NocoDB Leadler tablosundan lead listesi okur. Opsiyonel asama filtresi: "
        "Yeni/Soguk/Ilik/Sicak/Teklif/Sozlesme/Kazanildi/Kayip/Arsiv. "
        "limit varsayilan 10, max 50."
    ),
)
async def customer_search_leads(
    asama: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    return await _customer_search_leads_impl(asama=asama, limit=limit)


@function_tool(
    name_override="customer_get_lead",
    description_override=(
        "NocoDB Leadler tablosundan tek bir lead'i ID ile okur. "
        "Lead bulunmazsa NOT_FOUND doner."
    ),
)
async def customer_get_lead(lead_id: int) -> dict[str, Any]:
    return await _customer_get_lead_impl(lead_id=lead_id)


@function_tool(
    name_override="customer_get_pipeline_summary",
    description_override=(
        "NocoDB Pipeline tablosundan satis hunisinin asama bazli ozet sayilarini "
        "ve toplam kazanilan gelir toplamini doner."
    ),
)
async def customer_get_pipeline_summary() -> dict[str, Any]:
    return await _customer_get_pipeline_summary_impl()


def get_customer_tools() -> list[FunctionTool]:
    """customer_agent ve orchestrator tarafindan kullanilan tool listesi."""
    return [
        customer_search_leads,
        customer_get_lead,
        customer_get_pipeline_summary,
    ]


__all__ = [
    "customer_search_leads",
    "customer_get_lead",
    "customer_get_pipeline_summary",
    "get_customer_tools",
    # Test edilebilir impl'ler
    "_customer_search_leads_impl",
    "_customer_get_lead_impl",
    "_customer_get_pipeline_summary_impl",
    "_build_nocodb_client",
]
