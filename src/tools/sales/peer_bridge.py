"""Sales Director → peer agent köprü tool'ları.

Şeyma'nın 2026-05-22 isteği: "Reklam Uzmanı iletişimi olacak, ondan bilgi
alabilecek." Bu modül Sales Direktörü'nün diğer müdürlere (şu an sadece
Reklam Uzmanı) senkron sorgu atıp structured cevap aldığı tool'ları sağlar.

Mimari: Peer-via-direct-invoke. Sales Director bir LLM round'unda
`ask_reklam_uzmani(question, business_id)` çağırır. Tool içinde Reklam
Uzmanı agent'ı yaratılıp Runner.run ile çalıştırılır; cevap structured
dict olarak Sales Director'a döner — handoff yok, conversational pattern
yok. Bu sayede Sales Director'un analitik raporunda Reklam Uzmanı verisi
gerçek zamanlı kullanılabilir.

Loglama: Şef her zaman bu çağrıyı `tool_call` event'inde görür (Agents
SDK CliLoggingHooks otomatik). Yani "Sales → Reklam Uzmanı doğrudan
konuştu" görünür kalır.

Maliyet: 1 ekstra LLM call. Sadece Sales Director ihtiyaç duyduğunda
çağrılır (analitik soru gelir gelmez değil) — instructions LLM'i sınırlar.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents import Runner, function_tool


log = logging.getLogger(__name__)


# Senkron tool için makul üst limit — Reklam Uzmanı NocoDB tool'larını
# çağırabilir, en kötü senaryo birkaç saniyelik LLM round'u + 2-3 NocoDB
# fetch. 30sn yeterli, 60sn UI'de can sıkar.
_DEFAULT_TIMEOUT_SECONDS = 30.0


def _validate_question(question: str | None) -> dict[str, Any] | None:
    """Boş veya çok uzun soru reddet."""
    if not question or not question.strip():
        return {
            "success": False,
            "error": "question is required",
            "summary_tr": (
                "Hata: Reklam Uzmanı'na soru gönderemedin — soru boş. "
                "Neyi öğrenmek istediğini netleştir."
            ),
        }
    if len(question) > 2000:
        return {
            "success": False,
            "error": "question too long (>2000 chars)",
            "summary_tr": "Hata: Soru çok uzun, kısalt.",
        }
    return None


def _validate_business_id(business_id: str | None) -> dict[str, Any] | None:
    """business_id boş reddet — Reklam Uzmanı NocoDB sorgusu yapacak,
    işletme kontekstine ihtiyacı var."""
    if not business_id or not business_id.strip():
        return {
            "success": False,
            "error": "business_id is required",
            "summary_tr": (
                "Hata: business_id verilmedi. Hangi işletme için reklam "
                "verisi istediğini netleştir."
            ),
        }
    return None


async def _ask_reklam_uzmani_impl(
    question: str,
    business_id: str,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Sales Director → Reklam Uzmanı senkron sorgu.

    Args:
        question: Sales Director'un sorduğu soru (TR, kısa).
        business_id: Hangi işletme için (NocoDB filter'ları için zorunlu).
        timeout_seconds: Override (default 30s).

    Returns:
        dict: {success, answer, source, business_id, summary_tr} veya
        hata durumunda {success: False, error, summary_tr}.
    """
    if (err := _validate_question(question)):
        return err
    if (err := _validate_business_id(business_id)):
        return err

    q = question.strip()
    bid = business_id.strip()
    timeout = timeout_seconds or _DEFAULT_TIMEOUT_SECONDS

    # Lazy import — modül yüklenirken Reklam Uzmanı agent'ını init etme
    # (circular import + Agent oluşturma maliyeti). Tool çağrılınca yarat.
    try:
        from src.agents.sales.reklam_uzmani_agent import create_reklam_uzmani_agent
    except Exception as exc:
        log.error("ask_reklam_uzmani: import failed: %s", exc)
        return {
            "success": False,
            "error": f"reklam_uzmani import failed: {exc}",
            "summary_tr": (
                "Hata: Reklam Uzmanı modülü yüklenemedi. Şef'e raporla."
            ),
        }

    try:
        agent = create_reklam_uzmani_agent()
    except Exception as exc:
        log.error("ask_reklam_uzmani: agent create failed: %s", exc)
        return {
            "success": False,
            "error": f"reklam_uzmani agent create failed: {exc}",
            "summary_tr": (
                "Hata: Reklam Uzmanı başlatılamadı. Şef'e raporla."
            ),
        }

    # Soruyu işletme kontekstiyle zenginleştir — Reklam Uzmanı'nın
    # business_id'yi parametre olarak görmesi için.
    enriched_input = (
        f"[BUSINESS_ID: {bid}]\n"
        f"[PEER_REQUEST_FROM: sales_manager]\n\n"
        f"{q}\n\n"
        "Cevabını kısa tut (max 3-4 cümle). Sayısal veri varsa NocoDB "
        "tool ile doğrula. Tahmin/uydurma yok."
    )

    try:
        result = await asyncio.wait_for(
            Runner.run(starting_agent=agent, input=enriched_input),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning(
            "ask_reklam_uzmani: timeout after %.1fs business=%s", timeout, bid
        )
        return {
            "success": False,
            "error": f"timeout after {timeout:.0f}s",
            "summary_tr": (
                f"Hata: Reklam Uzmanı {timeout:.0f}sn içinde cevap vermedi. "
                "Sorunu kısalt veya Şef'e raporla."
            ),
        }
    except Exception as exc:
        log.error("ask_reklam_uzmani: run failed business=%s: %s", bid, exc)
        return {
            "success": False,
            "error": str(exc),
            "summary_tr": (
                "Hata: Reklam Uzmanı sorguya cevap veremedi. Şef'e raporla."
            ),
        }

    answer = getattr(result, "final_output", None)
    if not answer:
        return {
            "success": False,
            "error": "reklam_uzmani returned empty output",
            "summary_tr": "Hata: Reklam Uzmanı boş cevap verdi.",
        }

    return {
        "success": True,
        "answer": str(answer),
        "source": "reklam_uzmani",
        "business_id": bid,
        "question": q,
        "summary_tr": str(answer),
    }


ask_reklam_uzmani = function_tool(
    name_override="ask_reklam_uzmani",
    description_override=(
        "Sales Director only. Ask the Reklam Uzmanı (Ad Specialist) a "
        "synchronous question about Meta/Facebook Lead Ads campaigns, "
        "ad-source attribution, CPL, or which campaigns brought hot leads. "
        "Reklam Uzmanı queries NocoDB (Leadler with kaynak filter) and "
        "returns a short factual answer. Use this when the user asks "
        "'hangi reklamdan en çok lead geldi', 'CPL ne', 'reklamlar hangi "
        "kanaldan dönüyor' etc. Required: question (TR), business_id. "
        "Do NOT use for posting decisions — that's Pazarlama Müdürü."
    ),
)(_ask_reklam_uzmani_impl)


def get_peer_bridge_tools() -> list:
    """All peer bridge tools for Sales Director."""
    return [ask_reklam_uzmani]


__all__ = [
    "ask_reklam_uzmani",
    "get_peer_bridge_tools",
    "_ask_reklam_uzmani_impl",
]
