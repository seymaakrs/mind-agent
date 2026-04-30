"""Clay (B2B prospecting) tools for the Sales Customer Agent.

These tools are split into two layers:

1. **Pure logic** (no external I/O): ``score_business_presence``,
   ``generate_outreach_message``. Deterministic, fully tested, never touches
   the network.

2. **Discovery** (external I/O): ``discover_local_businesses``. Wraps a Clay
   client (REST or via n8n bridge to Clay MCP). The current implementation
   raises NotImplementedError when no Clay backend is configured — the agent
   surfaces this as a structured error so the LLM understands it cannot
   discover until config is provided.

Wiring options for the discovery layer (decide at deployment time):

    Option A — n8n bridge:  POST {n8n}/clay/search  →  Clay MCP  →  JSON list
    Option B — Clay REST:   POST api.clay.com/...   →  JSON list

Both are drop-in: the tool's contract is identical. To wire either, set
``CLAY_BACKEND_URL`` and ``CLAY_BACKEND_TOKEN`` env vars; the helper
``_call_clay_backend`` handles the HTTP.
"""
from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from agents import function_tool

from src.infra.errors import ServiceError, classify_error


# ---------------------------------------------------------------------------
# Constants — Zernio agent-spec scoring rules
# ---------------------------------------------------------------------------

# Sectors we target in Bodrum/Muğla (Slowdays focus)
TARGET_SECTORS = (
    "otel",
    "restoran",
    "cafe",
    "kafe",
    "butik",
    "perakende",
    "turizm",
    "e-ticaret",
)


# ---------------------------------------------------------------------------
# Pure logic tool: lead scoring
# ---------------------------------------------------------------------------


@function_tool
async def score_business_presence(
    business_name: str,
    has_website: bool,
    has_instagram: bool,
    instagram_follower_count: int = 0,
    google_rating: float | None = None,
    google_review_count: int = 0,
) -> dict[str, Any]:
    """Bir işletmenin dijital varlığına göre lead skoru üretir.

    Zernio agent spec'i kuralları:
        - Web yok + Instagram zayıf -> 10 (en yüksek ihtiyaç)
        - Sadece biri zayıf -> 7
        - Her şey var ama iyileştirilebilir -> 5
        - Her şey güçlü -> 3 (kritik değil)

    "Zayıf Instagram" = takipçi < 500 veya Instagram yok.

    Args:
        business_name: İşletme adı (log için).
        has_website: Web sitesi var mı.
        has_instagram: Instagram hesabı var mı.
        instagram_follower_count: IG takipçi (0 = yok).
        google_rating: Google puanı (1-5, opsiyonel).
        google_review_count: Google review sayısı (0 = yok).

    Returns:
        ``{"score": int, "rationale": str, "weak_areas": list[str]}``
    """
    weak_areas: list[str] = []
    weak_website = not has_website
    weak_instagram = (not has_instagram) or instagram_follower_count < 500

    if weak_website:
        weak_areas.append("website")
    if weak_instagram:
        weak_areas.append("instagram")

    # Google data is only considered when caller actually supplied a rating.
    # google_review_count alone (default 0) is ambiguous — "no data fetched"
    # vs "real zero" — so we treat it as missing unless rating is also given.
    google_data_provided = google_rating is not None
    if google_data_provided:
        if google_rating < 4.0:
            weak_areas.append("google_reputation")
        if google_review_count < 10:
            weak_areas.append("google_reviews")

    if weak_website and weak_instagram:
        score = 10
        rationale = (
            f"{business_name}: hem web sitesi yok hem Instagram varlığı zayıf "
            f"(takipçi: {instagram_follower_count}). En yüksek ihtiyaç."
        )
    elif weak_website or weak_instagram:
        score = 7
        weak = "website" if weak_website else "instagram"
        rationale = f"{business_name}: {weak} zayıf, diğeri var. Orta-yüksek ihtiyaç."
    elif google_data_provided and (
        google_rating < 4.0 or google_review_count < 10
    ):
        score = 5
        rationale = (
            f"{business_name}: dijital varlık var ama Google reputation "
            f"iyileştirilebilir (puan: {google_rating}, review: {google_review_count})."
        )
    else:
        score = 3
        rationale = (
            f"{business_name}: dijital olarak güçlü. Yeni hizmet veya "
            f"upsell odaklı yaklaşım uygun."
        )

    return {
        "success": True,
        "business_name": business_name,
        "score": score,
        "rationale": rationale,
        "weak_areas": weak_areas,
    }


# ---------------------------------------------------------------------------
# Pure logic tool: outreach message generator (CBO-compliant)
# ---------------------------------------------------------------------------


# Single source of truth for forbidden phrases — used by validators too.
FORBIDDEN_PHRASES = (
    "son şans",
    "hemen al",
    "kaçırma",
    "acele et",
    "fırsatı kaçırma",
)


def _turkish_lower(text: str) -> str:
    """Lowercase that handles Turkish dotted/dotless I correctly.

    Python's str.lower() maps Latin "I" -> "i" (with dot) instead of the
    Turkish "ı" (dotless), and "İ" -> "i̇" (with combining mark) instead of
    plain "i". This breaks substring matches against Turkish forbidden
    phrases. Apply Turkish-aware folding before .lower().
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


def _is_cbo_compliant(text: str) -> tuple[bool, list[str]]:
    """Return (compliant, list_of_violations)."""
    lower = _turkish_lower(text)
    hits = [p for p in FORBIDDEN_PHRASES if p in lower]
    return (len(hits) == 0, hits)


@function_tool
async def generate_outreach_message(
    business_name: str,
    sector: str,
    weak_areas: list[str],
    location: str = "Bodrum",
    tone: Literal["value", "soft", "direct"] = "value",
) -> dict[str, Any]:
    """CBO-uyumlu kişiselleştirilmiş outreach mesajı üretir.

    Üç ton:
      - ``value``: değer odaklı (önerilir, %5-15 yanıt oranı)
      - ``soft``: yumuşak ilk temas (durum tespiti)
      - ``direct``: doğrudan teklif (düşük yanıt oranı)

    Yasakli ifadeleri ASLA içermez (CBO standardı).

    Returns:
        ``{"success": True, "message": str, "tone": str, "cbo_compliant": bool}``.
    """
    sector_clean = sector.lower().strip()
    weak_phrase = ""
    if "website" in weak_areas and "instagram" in weak_areas:
        weak_phrase = "web sitesi ve Instagram"
    elif "website" in weak_areas:
        weak_phrase = "web sitesi"
    elif "instagram" in weak_areas:
        weak_phrase = "Instagram"

    if tone == "value":
        if weak_phrase:
            body = (
                f"Merhaba {business_name},\n\n"
                f"{location}'daki {sector_clean} işletmelerini takip ediyorum. "
                f"{business_name} için {weak_phrase} tarafında değer katabileceğimize inanıyorum.\n\n"
                "İsterseniz size özel ücretsiz bir dijital analiz hazırlayabiliriz — "
                "5 dakika sürer, somut öneriler sunar.\n\n"
                "Birlikte büyüyelim. 🌱\n"
                "— Şeyma, MindID"
            )
        else:
            body = (
                f"Merhaba {business_name},\n\n"
                f"{location}'daki {sector_clean} işletmelerinin dijital büyümesini "
                f"takip ediyorum. Mevcut kurulumunuz iyi durumda, ama bir sonraki "
                "seviyeye taşımak için fikirlerimiz var.\n\n"
                "Ücretsiz bir konuşma — değer katabilirsek devam ederiz.\n\n"
                "Birlikte büyüyelim. 🌱\n"
                "— Şeyma, MindID"
            )
    elif tone == "soft":
        body = (
            f"Merhaba {business_name},\n\n"
            f"{location} bölgesindeki işletmelerle ilgili bir araştırma yapıyorum. "
            "Sizin için şu an dijital tarafta en büyük zorluk ne?\n\n"
            "Anlamak isterim — belki bir sonraki adımı birlikte düşünebiliriz.\n\n"
            "İyi günler dilerim.\n"
            "— Şeyma"
        )
    else:  # direct
        body = (
            f"Merhaba {business_name},\n\n"
            f"{location}'daki {sector_clean} işletmelerine özel "
            f"AI üretimi içerik + otomatik lead sistemi kuruyoruz. "
            f"İlk ay sonuç yoksa para iadesi.\n\n"
            "Detayları konuşalım mı?\n"
            "— Şeyma, MindID"
        )

    compliant, hits = _is_cbo_compliant(body)
    return {
        "success": True,
        "business_name": business_name,
        "tone": tone,
        "message": body,
        "cbo_compliant": compliant,
        "violations": hits,
    }


# ---------------------------------------------------------------------------
# Discovery tool — Clay backend (n8n bridge or Clay REST)
# ---------------------------------------------------------------------------


CLAY_BACKEND_URL_ENV = "CLAY_BACKEND_URL"
CLAY_BACKEND_TOKEN_ENV = "CLAY_BACKEND_TOKEN"


async def _call_clay_backend(
    location: str,
    sector: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Internal: HTTP call to whatever clay backend is configured.

    Designed so we can swap n8n/Clay REST without touching the tool surface.
    Raises ServiceError on HTTP errors so the tool returns classified errors.
    """
    url = os.getenv(CLAY_BACKEND_URL_ENV)
    token = os.getenv(CLAY_BACKEND_TOKEN_ENV)
    if not url:
        raise NotImplementedError(
            f"Clay discovery backend not configured. Set {CLAY_BACKEND_URL_ENV} "
            f"to your n8n Clay-bridge endpoint or Clay REST endpoint."
        )

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = {
        "location": location,
        "sector": sector,
        "limit": limit,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else None
            text = exc.response.text if exc.response else str(exc)
            raise ServiceError(
                f"Clay backend HTTP {status}: {text}",
                status_code=status,
                service="clay",
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceError(
                f"Clay backend network error: {exc}",
                status_code=None,
                service="clay",
            ) from exc

    data = resp.json()
    if isinstance(data, dict):
        return list(data.get("businesses", data.get("data", [])))
    if isinstance(data, list):
        return data
    return []


@function_tool
async def discover_local_businesses(
    location: str = "Bodrum",
    sector: str = "otel",
    limit: int = 20,
) -> dict[str, Any]:
    """Bir konumdaki belirli sektördeki işletmeleri keşfeder (Clay üzerinden).

    Args:
        location: Şehir/bölge ("Bodrum", "Muğla", "Marmaris", ...).
        sector: Sektör ("otel", "restoran", "cafe", "butik", ...).
        limit: 1-50 arası, max 50.

    Returns:
        ``{"success": True, "count": int, "businesses": list[dict]}`` veya
        ``{"success": False, "error_code": str, "error": str}``.

    Notes:
        Discovery backend ortam değişkenlerinden alınır. Henüz konfigüre
        değilse ``error_code: "NOT_FOUND"`` döner — agent bunu kullanıcıya
        anlatır.
    """
    if sector.lower() not in TARGET_SECTORS:
        return {
            "success": False,
            "error": f"Sector '{sector}' is outside target list: {list(TARGET_SECTORS)}",
            "error_code": "INVALID_INPUT",
            "retryable": False,
        }
    capped = max(1, min(50, limit))
    try:
        businesses = await _call_clay_backend(location, sector, capped)
        return {
            "success": True,
            "count": len(businesses),
            "businesses": businesses,
        }
    except NotImplementedError as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "NOT_FOUND",
            "retryable": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, **classify_error(exc, "clay")}


__all__ = [
    "score_business_presence",
    "generate_outreach_message",
    "discover_local_businesses",
    "FORBIDDEN_PHRASES",
    "TARGET_SECTORS",
    "_is_cbo_compliant",
]
