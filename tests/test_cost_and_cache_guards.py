"""Maliyet limitörleri + cache guard testleri (2026-06-10 iyileştirme PR'ı).

Kapsam:
  1. CORS origin'leri env'den okunur (CORS_ALLOW_ORIGINS).
  2. Orchestrator Runner.run'a açık max_turns geçilir (ORCHESTRATOR_MAX_TURNS).
  3. Token bütçesi aşılırsa uyarı loglanır (MAX_TOKENS_PER_TASK).
  4. Brand identity TTL cache: tekrarlanan okuma Firestore'a gitmez,
     save sonrası cache invalidate edilir.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.config import Settings


# ---------------------------------------------------------------------------
# 1. Settings — CORS + maliyet limitleri
# ---------------------------------------------------------------------------


def test_settings_cors_default_is_wildcard(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    s = Settings.from_env()
    assert s.cors_origins_list == ["*"]


def test_settings_cors_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "https://app.mindidai.com.tr, https://mindid.web.app",
    )
    s = Settings.from_env()
    assert s.cors_origins_list == [
        "https://app.mindidai.com.tr",
        "https://mindid.web.app",
    ]


def test_settings_cost_guard_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("ORCHESTRATOR_MAX_TURNS", raising=False)
    monkeypatch.delenv("MAX_TOKENS_PER_TASK", raising=False)
    s = Settings.from_env()
    assert s.orchestrator_max_turns == 20
    assert s.max_tokens_per_task == 300_000


def test_settings_cost_guard_env_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ORCHESTRATOR_MAX_TURNS", "5")
    monkeypatch.setenv("MAX_TOKENS_PER_TASK", "100000")
    s = Settings.from_env()
    assert s.orchestrator_max_turns == 5
    assert s.max_tokens_per_task == 100_000


# ---------------------------------------------------------------------------
# 2 + 3. Orchestrator runner — max_turns + token bütçesi uyarısı
# ---------------------------------------------------------------------------


def _fake_run_result(total_tokens: int = 1000):
    return SimpleNamespace(
        final_output="ok",
        to_input_list=lambda: [],
        context_wrapper=SimpleNamespace(
            usage=SimpleNamespace(total_tokens=total_tokens)
        ),
    )


@pytest.mark.asyncio
async def test_runner_called_with_explicit_max_turns():
    from src.app import orchestrator_runner as orun

    run_mock = AsyncMock(return_value=_fake_run_result())
    with (
        patch.object(orun.Runner, "run", run_mock),
        patch.object(orun, "create_orchestrator", return_value=MagicMock()),
        patch.object(orun, "TaskLogger", MagicMock()),
        patch.object(orun, "CliLoggingHooks", MagicMock()),
    ):
        output, _ = await orun.run_orchestrator_async("merhaba")

    assert output == "ok"
    assert run_mock.call_count == 1
    kwargs = run_mock.call_args.kwargs
    assert kwargs["max_turns"] == orun._settings.orchestrator_max_turns


@pytest.mark.asyncio
async def test_token_budget_warning_logged_when_exceeded(caplog):
    from src.app import orchestrator_runner as orun

    budget = orun._settings.max_tokens_per_task
    run_mock = AsyncMock(return_value=_fake_run_result(total_tokens=budget + 1))
    with (
        patch.object(orun.Runner, "run", run_mock),
        patch.object(orun, "create_orchestrator", return_value=MagicMock()),
        patch.object(orun, "TaskLogger", MagicMock()),
        patch.object(orun, "CliLoggingHooks", MagicMock()),
        caplog.at_level(logging.WARNING, logger="src.app.orchestrator_runner"),
    ):
        await orun.run_orchestrator_async("merhaba")

    assert any("token" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_no_token_budget_warning_under_limit(caplog):
    from src.app import orchestrator_runner as orun

    run_mock = AsyncMock(return_value=_fake_run_result(total_tokens=10))
    with (
        patch.object(orun.Runner, "run", run_mock),
        patch.object(orun, "create_orchestrator", return_value=MagicMock()),
        patch.object(orun, "TaskLogger", MagicMock()),
        patch.object(orun, "CliLoggingHooks", MagicMock()),
        caplog.at_level(logging.WARNING, logger="src.app.orchestrator_runner"),
    ):
        await orun.run_orchestrator_async("merhaba")

    assert not any("token" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 4. Brand identity TTL cache
# ---------------------------------------------------------------------------


def _brand_doc(business_id: str = "biz1") -> dict:
    return {
        "business_id": business_id,
        "schema_version": 1,
    }


@pytest.fixture(autouse=True)
def _clean_brand_cache():
    from src.tools import brand

    brand.clear_brand_identity_cache()
    yield
    brand.clear_brand_identity_cache()


def test_load_brand_identity_uses_cache_on_second_call():
    from src.tools import brand

    doc_client = MagicMock()
    doc_client.get_document.return_value = _brand_doc()
    with patch.object(brand, "get_document_client", return_value=doc_client):
        first = brand.load_brand_identity("biz1")
        second = brand.load_brand_identity("biz1")

    assert first is not None
    assert second is not None
    assert doc_client.get_document.call_count == 1  # ikinci okuma cache'ten


def test_load_brand_identity_missing_doc_not_cached():
    from src.tools import brand

    doc_client = MagicMock()
    doc_client.get_document.return_value = None
    with patch.object(brand, "get_document_client", return_value=doc_client):
        assert brand.load_brand_identity("biz-yok") is None
        assert brand.load_brand_identity("biz-yok") is None

    # None sonucu cache'lenmez — yeni oluşturulan kimlik hemen görünmeli
    assert doc_client.get_document.call_count == 2


def test_save_brand_identity_invalidates_cache():
    from src.infra.brand_identity import BrandIdentity
    from src.tools import brand

    doc_client = MagicMock()
    doc_client.get_document.return_value = _brand_doc()
    with patch.object(brand, "get_document_client", return_value=doc_client):
        brand.load_brand_identity("biz1")  # cache doldu
        bi = BrandIdentity.model_validate(_brand_doc())
        brand.save_brand_identity(bi)  # invalidate etmeli
        brand.load_brand_identity("biz1")  # tekrar Firestore'a gitmeli

    assert doc_client.get_document.call_count == 2


def test_cache_expires_after_ttl(monkeypatch):
    from src.tools import brand

    doc_client = MagicMock()
    doc_client.get_document.return_value = _brand_doc()
    fake_time = [1000.0]
    monkeypatch.setattr(brand.time, "monotonic", lambda: fake_time[0])
    with patch.object(brand, "get_document_client", return_value=doc_client):
        brand.load_brand_identity("biz1")
        fake_time[0] += brand._BRAND_CACHE_TTL_SECONDS + 1
        brand.load_brand_identity("biz1")

    assert doc_client.get_document.call_count == 2
