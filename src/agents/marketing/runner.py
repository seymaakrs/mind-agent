"""Marketing Dispatcher (Pazarlamaci Runner) — Cloud Run Job entry-point.

Periyodik calisir (saatte bir veya gunde bir). Firestore'dan aktif planlari
ve bugun icin planlanmis postlari okur. Her isletme icin Orchestrator'i
cagirir; Orchestrator Pazarlamaci'ya devreder, Pazarlamaci mevcut workflow
ile planli postu uretir + Instagram'a atar + plan kaydini guncellestirir.

Bu dispatcher LLM yapmaz — sadece:
1. Hangi isletmenin bugun planli postu var? (Firestore query)
2. O isletmeyi Orchestrator'a yonlendir.

Run:
    python -m src.agents.marketing.runner

Cloud Run Job (one-shot — bir kez calistir, exit):
    RUN_ONCE=true python -m src.agents.marketing.runner

Scheduler onerisi: gunde 1 kez sabah 08:00 (Europe/Istanbul) veya saatte
bir (eger plan post'larinda saat-bazli scheduling eklenirse). Su an
gunluk yeterli — Pazarlamaci tum bugunki postlari tek calistirmada atar.

NOT: Plan post'larina `scheduled_hour` field'i eklenirse (TODO), bu
runner saatlik calisip sadece o saatin postlarini tetikleyecek.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any


log = logging.getLogger("marketing_dispatcher")

_PAUSE_NO_BUSINESS_SEC = 3600  # 1 saat
_PAUSE_ERROR_SEC = 300         # 5 dk

# Dispatch prompt — Orchestrator Pazarlamaci'ya devreder
_DISPATCH_PROMPT = (
    "Plana gore bugun icin planlanmis postlari calistir. "
    "Eger today posts varsa: her birini sirayla uret + Instagram'a at + "
    "plan kaydini status='posted' yap. Eger today posts yoksa: sessizce "
    "raporla 'bugun planli post yok' de ve dur. Plan olusturma, plan "
    "ekleme yapma — sadece var olanlari calistir."
)


async def _get_active_business_ids() -> list[str]:
    """Firestore /businesses koleksiyonundan aktif (silinmemis) isletme ID'leri.

    Veri sema: businesses/{id} dokumaninda 'status' field opsiyonel —
    'deleted' / 'archived' ise atlanir. status yok / 'approved' / None
    ise aktif sayilir.
    """
    try:
        from src.infra.firebase_client import get_document_client

        biz_client = get_document_client("businesses")
        docs = biz_client.query_documents(field="status", operator="!=", value="deleted", limit=200)
        if not docs:
            # Fallback: status field set degilse query bos doner. List all.
            docs = biz_client.list_documents(limit=200)
    except Exception as exc:
        log.warning("marketing_dispatcher: business list query failed: %s", exc)
        return []

    ids: list[str] = []
    for doc in docs:
        # Skip archived/deleted
        status = (doc.get("status") or "").lower()
        if status in ("deleted", "archived"):
            continue
        # documentId or id
        biz_id = doc.get("documentId") or doc.get("id")
        if biz_id:
            ids.append(str(biz_id))
    return ids


async def _business_has_planned_post_today(business_id: str) -> bool:
    """Hizli filtre: bugun icin planlanmis post var mi?

    Optimization: Orchestrator'i bos cagirmayalim. Sadece isi olan
    isletmeleri tetikle. Hata olursa True don (defansif — Orchestrator'a
    devret, o "post yok" derse zaten skip eder).
    """
    try:
        from src.infra.firebase_client import get_document_client

        plans_client = get_document_client(f"businesses/{business_id}/marketing_plans")
        # Aktif plan var mi?
        plans = plans_client.query_documents(
            field="status", operator="==", value="active", limit=10
        )
        if not plans:
            return False

        today = datetime.now(timezone.utc).date().isoformat()
        # Her plan icindeki 'posts' listesinde bugun + planned var mi?
        for plan in plans:
            posts = plan.get("posts") or []
            for post in posts:
                if (
                    post.get("scheduled_date") == today
                    and post.get("status") == "planned"
                ):
                    return True
        return False
    except Exception as exc:
        log.warning(
            "marketing_dispatcher: planned-posts check failed for %s: %s — defansif True",
            business_id, exc,
        )
        return True


async def dispatch_for_business(business_id: str) -> dict[str, Any]:
    """Tek bir isletme icin Orchestrator'i cagir.

    Orchestrator marketing_agent_tool ile Pazarlamaci'yi tetikler.
    Pazarlamaci get_todays_posts -> her biri icin image_agent/video_agent +
    post_on_instagram + update_post_in_plan akisini kosturur.

    Returns: orchestrator final output + meta info.
    """
    try:
        from src.app.orchestrator_runner import run_orchestrator_async
    except ImportError as exc:
        log.error("marketing_dispatcher: orchestrator import failed: %s", exc)
        return {"business_id": business_id, "success": False, "error": str(exc)}

    log.info("marketing_dispatcher: dispatching business=%s", business_id)
    try:
        output, log_path = await run_orchestrator_async(
            user_input=_DISPATCH_PROMPT,
            context={"business_id": business_id},
        )
        log.info(
            "marketing_dispatcher: business=%s OK output_preview=%r log=%s",
            business_id, (output or "")[:120], log_path,
        )
        return {
            "business_id": business_id,
            "success": True,
            "output": output,
            "log_path": log_path,
        }
    except Exception as exc:
        log.exception("marketing_dispatcher: business=%s FAILED: %s", business_id, exc)
        return {"business_id": business_id, "success": False, "error": str(exc)}


async def tick() -> dict[str, Any]:
    """Tek bir dispatch turu — Cloud Run Job entry point.

    Returns: aggregated stats (kac isletme tetiklendi, kac basari).
    """
    business_ids = await _get_active_business_ids()
    if not business_ids:
        log.info("marketing_dispatcher: aktif isletme yok")
        return {"businesses_total": 0, "dispatched": 0, "succeeded": 0, "failed": 0}

    log.info("marketing_dispatcher: %d aktif isletme bulundu", len(business_ids))

    dispatched = 0
    succeeded = 0
    failed = 0
    skipped_no_posts = 0

    for biz_id in business_ids:
        if not await _business_has_planned_post_today(biz_id):
            skipped_no_posts += 1
            continue
        dispatched += 1
        result = await dispatch_for_business(biz_id)
        if result.get("success"):
            succeeded += 1
        else:
            failed += 1

    summary = {
        "businesses_total": len(business_ids),
        "dispatched": dispatched,
        "succeeded": succeeded,
        "failed": failed,
        "skipped_no_posts": skipped_no_posts,
    }
    log.info("marketing_dispatcher: tick complete %s", summary)
    return summary


async def loop(*, max_iterations: int | None = None) -> None:
    """Marketing dispatcher loop. ``max_iterations`` is for tests + one-shot mode."""
    log.info(
        "marketing_dispatcher starting: max_iter=%s",
        max_iterations or "infinite",
    )

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            summary = await tick()
            if max_iterations == 1:
                log.info("marketing_dispatcher: one-shot mode exiting (%s)", summary)
                return
            await asyncio.sleep(_PAUSE_NO_BUSINESS_SEC)
        except Exception as exc:
            log.exception("marketing_dispatcher: tick failed: %s", exc)
            if max_iterations == 1:
                return
            await asyncio.sleep(_PAUSE_ERROR_SEC)


def _install_sigterm_handler() -> None:
    def _stop(*_: object) -> None:
        log.info("marketing_dispatcher: SIGTERM received")

    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except ValueError:
        pass


def _resolve_max_iterations() -> int | None:
    """Cloud Run Job mode: RUN_ONCE=true env -> max_iterations=1."""
    if os.environ.get("RUN_ONCE", "").lower() in ("1", "true", "yes"):
        return 1
    return None


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _install_sigterm_handler()
    try:
        asyncio.run(loop(max_iterations=_resolve_max_iterations()))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
