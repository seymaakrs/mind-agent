"""Sales knowledge tools — Satış Direktörü'nün ürün/hizmet/hedef-kitle hakimiyeti.

Şeyma'nın isteği (2026-05-22): "Sales Manager yaptığımız iş hakkında tam donanımlı
bilgi sahibi olmalı. Hedef kitleyi iyi tanımalı. Sattığı ürüne hakimiyeti kadar
bilgiyi aktarması çok önemli."

Bu modul Satış Direktörü agent'ının BrandIdentity Firestore dokumanından
ürün/hizmet, hedef kitle, ton ve USP bilgisini structured okuduğu 5 read-only
tool sağlar. Tool'lar pure read — yazma yetkisi YOK. Brand identity henüz
oluşturulmamışsa structured "exists: False" dönerler (sessiz fail yok).

Pattern: src/tools/sales/reporting_tools.py paritesi (pure async _impl +
function_tool wrapper + get_*_tools factory).

Disiplin kuralı: business_id boş gelirse tool çağrıyı reddeder (kullanıcıya
net hata). LLM yanlışlıkla business_id atlamasın diye zorunlu argüman.

İş bağlamı kapısı (2026-05-24): BrandBusinessContext.enabled=False iken
get_product_catalog / get_unique_value_proposition tool'ları "henüz aktif
edilmedi" döner ve LLM uydurmaya kalkmaz. get_sales_playbook ise business
context bölümünü gizler ama diğer alanları (audience/voice) döndürmeye
devam eder.
"""
from __future__ import annotations

import logging
from typing import Any

from agents import function_tool

from src.tools.brand import load_brand_identity


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_business_id(business_id: str | None) -> dict[str, Any] | None:
    """business_id boş ise structured error döndür, yoksa None."""
    if not business_id or not business_id.strip():
        return {
            "success": False,
            "error": "business_id is required",
            "summary_tr": (
                "Hata: business_id verilmedi. Hangi işletme için bilgi "
                "istediğini netleştir."
            ),
        }
    return None


def _brand_missing_response(business_id: str, tool_name: str) -> dict[str, Any]:
    """Brand identity yoksa standart 'exists=False' cevabı."""
    return {
        "success": True,
        "business_id": business_id,
        "exists": False,
        "tool": tool_name,
        "summary_tr": (
            f"İşletme {business_id} için brand identity henüz tanımlanmamış. "
            f"Şeyma BrandIdentity'i mind-id portal 'Marka Kimliği' "
            f"sayfasından doldurmalı."
        ),
    }


def _business_context_disabled_response(
    business_id: str, tool_name: str
) -> dict[str, Any]:
    """İş Bağlamı bölümü kullanıcı tarafından aktif edilmediyse döner.

    LLM'in bu cevabı görünce ürün/USP/rakip bilgisi UYDURMAMASI gerekiyor.
    Kullanıcıya 'mind-id portal > Marka Kimliği > İş Bağlamı bölümünü
    aktif edin' yönlendirmesi yap.
    """
    return {
        "success": True,
        "business_id": business_id,
        "exists": True,
        "business_context_enabled": False,
        "tool": tool_name,
        "summary_tr": (
            "İş Bağlamı bölümü bu işletme için henüz aktif edilmedi. "
            "Ürün/hizmet, USP, rakip ve SEO bilgileri ajan tarafından "
            "okunmuyor. Aktif etmek için: mind-id portal > Marka Kimliği "
            "> İş Bağlamı > 'Ajanlar için aç' toggle'ı. Bu cevap geldiğinde "
            "ÜRÜN/USP/RAKİP HAKKINDA TAHMİN YÜRÜTME — kullanıcıyı yönlendir."
        ),
    }


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _get_product_catalog_impl(business_id: str) -> dict[str, Any]:
    """Ürün/hizmet kataloğu + sektör + USP + rakipler."""
    err = _require_business_id(business_id)
    if err:
        return err
    bid = business_id.strip()
    bi = load_brand_identity(bid)
    if bi is None:
        return _brand_missing_response(bid, "get_product_catalog")

    if not bi.business_context.enabled:
        return _business_context_disabled_response(bid, "get_product_catalog")

    products = bi.business_context.products or []
    usp = bi.business_context.usp
    competitors = bi.business_context.competitors or []
    seo_keywords = bi.business_context.seo_keywords or []
    industry = bi.basics.industry
    tagline = bi.basics.tagline

    has_data = bool(products or usp or industry)
    if not has_data:
        return {
            "success": True,
            "business_id": bid,
            "exists": True,
            "has_product_data": False,
            "summary_tr": (
                "Brand identity var ama ürün/sektör/USP boş. Satış Direktörü "
                "müşteri sorusuna 'henüz bu bilgi tanımlanmadı' demeli, "
                "uydurma yapmamalı."
            ),
        }

    summary_lines = []
    if bi.basics.name:
        summary_lines.append(f"Marka: {bi.basics.name}")
    if industry:
        summary_lines.append(f"Sektör: {industry}")
    if tagline:
        summary_lines.append(f"Slogan: {tagline}")
    if products:
        summary_lines.append(f"Ürün/Hizmet ({len(products)}): " + ", ".join(products[:8]))
    if usp:
        summary_lines.append(f"USP: {usp}")
    if competitors:
        summary_lines.append(f"Rakipler: {', '.join(competitors[:5])}")

    return {
        "success": True,
        "business_id": bid,
        "exists": True,
        "has_product_data": True,
        "industry": industry,
        "brand_name": bi.basics.name,
        "tagline": tagline,
        "products": products,
        "usp": usp,
        "competitors": competitors,
        "seo_keywords": seo_keywords,
        "summary_tr": "\n".join(summary_lines),
    }


async def _get_target_audience_impl(business_id: str) -> dict[str, Any]:
    """Hedef kitle: rol, yaş, acılar (pain_points), coğrafya, dil."""
    err = _require_business_id(business_id)
    if err:
        return err
    bid = business_id.strip()
    bi = load_brand_identity(bid)
    if bi is None:
        return _brand_missing_response(bid, "get_target_audience")

    aud = bi.audience
    primary = aud.primary
    role = primary.role if primary else None
    age = primary.age_range if primary else None
    pains = list(primary.pain_points) if primary else []
    geo = list(aud.geo)
    langs = list(aud.languages)

    has_data = bool(role or age or pains or geo)
    if not has_data:
        return {
            "success": True,
            "business_id": bid,
            "exists": True,
            "has_audience_data": False,
            "summary_tr": (
                "Brand identity'de hedef kitle (audience.primary) boş. "
                "Satış Direktörü genel konuşma yerine 'hedef kitle tanımlanmadı' "
                "uyarısı vermeli — disiplinli."
            ),
        }

    parts = []
    if role:
        parts.append(f"Rol: {role}")
    if age:
        parts.append(f"Yaş: {age}")
    if pains:
        parts.append(f"Acılar: {'; '.join(pains[:5])}")
    if geo:
        parts.append(f"Coğrafya: {', '.join(geo)}")
    if langs:
        parts.append(f"Dil: {', '.join(langs)}")

    return {
        "success": True,
        "business_id": bid,
        "exists": True,
        "has_audience_data": True,
        "primary_role": role,
        "age_range": age,
        "pain_points": pains,
        "geo": geo,
        "languages": langs,
        "summary_tr": " | ".join(parts),
    }


async def _get_brand_voice_impl(business_id: str) -> dict[str, Any]:
    """Marka sesi — Satış Direktörü DM/cevap tonu kalibre eder."""
    err = _require_business_id(business_id)
    if err:
        return err
    bid = business_id.strip()
    bi = load_brand_identity(bid)
    if bi is None:
        return _brand_missing_response(bid, "get_brand_voice")

    voice = bi.voice
    has_data = bool(
        voice.tone or voice.personality or voice.avoid_words
        or voice.preferred_words or voice.example_captions
    )
    if not has_data:
        return {
            "success": True,
            "business_id": bid,
            "exists": True,
            "has_voice_data": False,
            "summary_tr": (
                "Brand voice boş. Sales Direktörü güvenli generic ton "
                "kullanmalı (samimi, profesyonel)."
            ),
        }

    parts = []
    if voice.tone:
        parts.append(f"Ton: {voice.tone}")
    if voice.personality:
        parts.append(f"Kişilik: {', '.join(voice.personality)}")
    if voice.cta_style:
        parts.append(f"CTA: {voice.cta_style}")
    if voice.avoid_words:
        parts.append(f"YASAK: {', '.join(voice.avoid_words[:8])}")
    if voice.preferred_words:
        parts.append(f"TERCİH: {', '.join(voice.preferred_words[:8])}")

    return {
        "success": True,
        "business_id": bid,
        "exists": True,
        "has_voice_data": True,
        "tone": voice.tone,
        "personality": list(voice.personality),
        "avoid_words": list(voice.avoid_words),
        "preferred_words": list(voice.preferred_words),
        "cta_style": voice.cta_style,
        "example_captions": list(voice.example_captions),
        "summary_tr": " | ".join(parts),
    }


async def _get_unique_value_proposition_impl(business_id: str) -> dict[str, Any]:
    """USP + diferansiyatör + içerik pillarları (satış pitch hazırlığı)."""
    err = _require_business_id(business_id)
    if err:
        return err
    bid = business_id.strip()
    bi = load_brand_identity(bid)
    if bi is None:
        return _brand_missing_response(bid, "get_unique_value_proposition")

    if not bi.business_context.enabled:
        return _business_context_disabled_response(
            bid, "get_unique_value_proposition"
        )

    usp = bi.business_context.usp
    tagline = bi.basics.tagline
    competitors = list(bi.business_context.competitors)
    pillars = list(bi.content_strategy.pillars)

    has_data = bool(usp or tagline or pillars)
    if not has_data:
        return {
            "success": True,
            "business_id": bid,
            "exists": True,
            "has_uvp_data": False,
            "summary_tr": (
                "USP / tagline / pillars boş. Satış Direktörü diferansiyatör "
                "olmadan satış pitch'i yapamaz — Şeyma'dan BrandIdentity "
                "doldurması istenmeli."
            ),
        }

    parts = []
    if tagline:
        parts.append(f"Slogan: {tagline}")
    if usp:
        parts.append(f"USP: {usp}")
    if pillars:
        parts.append(f"İçerik sütunları: {', '.join(pillars)}")
    if competitors:
        parts.append(f"Rakipten farkı: {', '.join(competitors[:3])} karşısında")

    return {
        "success": True,
        "business_id": bid,
        "exists": True,
        "has_uvp_data": True,
        "tagline": tagline,
        "usp": usp,
        "competitors": competitors,
        "content_pillars": pillars,
        "summary_tr": "\n".join(parts),
    }


async def _get_sales_playbook_impl(business_id: str) -> dict[str, Any]:
    """Tüm sales bilgisini TEK çağrıda döndüren atomik kompakt özet.

    LLM'in 4 ayrı tool çağırması yerine başında bunu çağırması daha ucuz
    (1 Firestore read, 1 LLM round). Detaya inmek isterse diğer 4 tool var.

    İş Bağlamı kapalıyken: products/usp/competitors boş döner, response'a
    business_context_enabled: False eklenir; completeness skoru bu alanlar
    olmadan hesaplanır.
    """
    err = _require_business_id(business_id)
    if err:
        return err
    bid = business_id.strip()
    bi = load_brand_identity(bid)
    if bi is None:
        return _brand_missing_response(bid, "get_sales_playbook")

    bc = bi.business_context
    aud = bi.audience
    primary = aud.primary

    bc_enabled = bc.enabled
    products = list(bc.products) if bc_enabled else []
    usp = bc.usp if bc_enabled else None
    competitors = list(bc.competitors) if bc_enabled else []

    completeness = {
        "has_products": bool(products),
        "has_usp": bool(usp),
        "has_audience": bool(primary and (primary.role or primary.pain_points)),
        "has_voice": bool(bi.voice.tone),
        "has_pillars": bool(bi.content_strategy.pillars),
    }
    completeness_score = sum(1 for v in completeness.values() if v)

    bc_note = (
        ""
        if bc_enabled
        else " | NOT: İş Bağlamı kapalı (ürün/USP/rakip okunmadı)."
    )

    return {
        "success": True,
        "business_id": bid,
        "exists": True,
        "business_context_enabled": bc_enabled,
        "brand_name": bi.basics.name,
        "industry": bi.basics.industry,
        "tagline": bi.basics.tagline,
        "products": products,
        "usp": usp,
        "competitors": competitors,
        "audience": {
            "role": primary.role if primary else None,
            "age_range": primary.age_range if primary else None,
            "pain_points": list(primary.pain_points) if primary else [],
            "geo": list(aud.geo),
            "languages": list(aud.languages),
        },
        "voice": {
            "tone": bi.voice.tone,
            "personality": list(bi.voice.personality),
            "avoid_words": list(bi.voice.avoid_words),
            "preferred_words": list(bi.voice.preferred_words),
            "cta_style": bi.voice.cta_style,
        },
        "content_pillars": list(bi.content_strategy.pillars),
        "completeness": completeness,
        "completeness_score": completeness_score,
        "is_ready_for_outreach": completeness_score >= 3,
        "summary_tr": (
            f"{bi.basics.name or '(isim yok)'} — {bi.basics.industry or '(sektör yok)'} | "
            f"Hazırlık skoru: {completeness_score}/5. "
            + (
                "Outreach için hazır."
                if completeness_score >= 3
                else "Outreach için eksik bilgi var — BrandIdentity'i tamamla."
            )
            + bc_note
        ),
    }


# ---------------------------------------------------------------------------
# function_tool wrapper'ları
# ---------------------------------------------------------------------------


get_product_catalog = function_tool(
    name_override="get_product_catalog",
    description_override=(
        "Returns the business product/service catalog, industry, tagline, USP, "
        "and competitors from BrandIdentity (Firestore). Use this BEFORE making "
        "any product claim. If `exists: false` or `has_product_data: false` or "
        "`business_context_enabled: false`, DO NOT invent product info — tell "
        "the user the data is missing or not yet activated. Required: business_id."
    ),
)(_get_product_catalog_impl)


get_target_audience = function_tool(
    name_override="get_target_audience",
    description_override=(
        "Returns the target audience profile: role, age range, pain points, "
        "geography, languages. Use this BEFORE crafting messages or campaign "
        "ideas. If `has_audience_data: false`, say so — do not guess audience. "
        "Required: business_id."
    ),
)(_get_target_audience_impl)


get_brand_voice = function_tool(
    name_override="get_brand_voice",
    description_override=(
        "Returns brand voice: tone, personality, avoid_words, preferred_words, "
        "cta_style. Use this BEFORE writing any DM, follow-up message, or "
        "external-facing copy. Required: business_id."
    ),
)(_get_brand_voice_impl)


get_unique_value_proposition = function_tool(
    name_override="get_unique_value_proposition",
    description_override=(
        "Returns USP, tagline, competitors, and content pillars. Use this when "
        "the user asks 'what makes us different' or when preparing a sales "
        "pitch. If `business_context_enabled: false`, DO NOT invent — direct "
        "the user to activate the section in mind-id portal. Required: business_id."
    ),
)(_get_unique_value_proposition_impl)


get_sales_playbook = function_tool(
    name_override="get_sales_playbook",
    description_override=(
        "Returns the full sales playbook in ONE call: products, USP, audience, "
        "voice, pillars, and a completeness score (0-5). Prefer this over "
        "calling the individual knowledge tools when you need overall context. "
        "If `business_context_enabled: false`, products/usp/competitors fields "
        "will be empty — surface this to the user. Required: business_id."
    ),
)(_get_sales_playbook_impl)


def get_knowledge_tools() -> list:
    """All sales knowledge (product/audience/voice/UVP) read tools."""
    return [
        get_product_catalog,
        get_target_audience,
        get_brand_voice,
        get_unique_value_proposition,
        get_sales_playbook,
    ]


__all__ = [
    "get_product_catalog",
    "get_target_audience",
    "get_brand_voice",
    "get_unique_value_proposition",
    "get_sales_playbook",
    "get_knowledge_tools",
    "_get_product_catalog_impl",
    "_get_target_audience_impl",
    "_get_brand_voice_impl",
    "_get_unique_value_proposition_impl",
    "_get_sales_playbook_impl",
]
