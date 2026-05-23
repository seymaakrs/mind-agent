"""H-5 — Faz 2 birim katmani 9 yeni tool icin input validation contract.

Sales Director'un alt birimlerine (Avcilik / CX / Kalite) verilen
9 yazma tool'unun parametre sinirlarini CI'da donduran snapshot test.

Regression olursa LLM, prod'da:
* gunluk outreach tavanini negatif/asiri yuksek set edebilir,
* template icerigini bos string'e cevirebilir,
* Guardian esiklerini ters siralayabilir (red >= yellow olur)
  -> Bekci RED state'e hic giremez, pause tetiklenmez.

Bu testler her bir guardrail'i tek tek pinler. Validation'a dokunan PR
testleri kirar; intentional ise testleri ayni commit'te guncellersin.
"""
from __future__ import annotations

import pytest

pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")

from src.tools.sales import management_tools as mt


VALID_REASON = "audit-trail-yeterli-uzunluk"


# ---------------------------------------------------------------------------
# Outreach Avcilik birimi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, -100, 501, 999, "10", 10.5, None])
async def test_outreach_set_daily_limit_rejects_out_of_range(bad, monkeypatch):
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "tbl_x")
    r = await mt._outreach_set_daily_limit_impl(new_limit=bad)
    assert r["success"] is False
    assert "new_limit" in (r.get("error", "") + r.get("user_message_tr", "")).lower()


@pytest.mark.asyncio
async def test_outreach_skip_lead_rejects_empty_reason(monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "tbl_x")
    r = await mt._outreach_skip_lead_impl(lead_id=42, reason="")
    assert r["success"] is False
    assert "reason" in r["error"].lower() or "sebep" in r["error"].lower()


# ---------------------------------------------------------------------------
# CX birimi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, 1001, 5000, None])
async def test_auto_reply_set_daily_cap_rejects_out_of_range(bad, monkeypatch):
    monkeypatch.setenv("NOCODB_SETTINGS_TABLE_ID", "tbl_x")
    r = await mt._auto_reply_set_daily_cap_impl(new_cap=bad)
    assert r["success"] is False
    assert "new_cap" in (r.get("error", "") + r.get("user_message_tr", "")).lower()


@pytest.mark.asyncio
async def test_auto_reply_template_update_rejects_empty_icerik(monkeypatch):
    monkeypatch.setenv("NOCODB_TEMPLATES_TABLE_ID", "tbl_x")
    r = await mt._auto_reply_template_update_impl(template_id=1, icerik="")
    assert r["success"] is False
    assert "icerik" in r["error"].lower() or "len" in r["error"].lower()


@pytest.mark.asyncio
async def test_flag_for_human_rejects_empty_reason(monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "tbl_x")
    r = await mt._flag_for_human_impl(lead_id=42, reason="")
    assert r["success"] is False


# ---------------------------------------------------------------------------
# Kalite birimi (Guardian)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guardian_rejects_red_geq_yellow(monkeypatch):
    """red < yellow olmali; aksi halde Bekci RED state'e giremez."""
    r = await mt._guardian_set_thresholds_impl(
        reply_rate_yellow=10.0,
        reply_rate_red=10.0,  # equal -> reject
    )
    assert r["success"] is False
    assert "less than" in r["error"].lower() or "kesin kucuk" in r["user_message_tr"].lower()

    r = await mt._guardian_set_thresholds_impl(
        reply_rate_yellow=5.0,
        reply_rate_red=15.0,  # red > yellow -> reject
    )
    assert r["success"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1.0, 100.1, 200.0])
async def test_guardian_rejects_out_of_range_thresholds(bad):
    r = await mt._guardian_set_thresholds_impl(
        reply_rate_yellow=bad,
        reply_rate_red=1.0,
    )
    assert r["success"] is False


@pytest.mark.asyncio
async def test_guardian_engagement_thresholds_must_come_as_pair():
    r = await mt._guardian_set_thresholds_impl(
        reply_rate_yellow=10.0,
        reply_rate_red=5.0,
        engagement_rate_yellow=20.0,
        engagement_rate_red=None,  # only one of pair -> reject
    )
    assert r["success"] is False
    assert "birlikte" in r["user_message_tr"].lower() or "pair" in r["error"].lower()


# ---------------------------------------------------------------------------
# Env-bound table-id guardrails (negative path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outreach_set_daily_limit_requires_settings_env(monkeypatch):
    monkeypatch.delenv("NOCODB_SETTINGS_TABLE_ID", raising=False)
    r = await mt._outreach_set_daily_limit_impl(new_limit=100)
    assert r["success"] is False


@pytest.mark.asyncio
async def test_outreach_skip_lead_requires_leads_env(monkeypatch):
    monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
    from src.app.config import get_settings
    get_settings.cache_clear()
    r = await mt._outreach_skip_lead_impl(lead_id=1, reason=VALID_REASON)
    get_settings.cache_clear()
    assert r["success"] is False
