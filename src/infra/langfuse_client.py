"""Langfuse observability entegrasyonu.

Her LLM cagrisini (token, cost, latency, prompt, output) Langfuse'a gonderir.
OpenInference instrumentation Agents SDK trace'lerini OTEL spanlarina cevirir;
Langfuse SDK bunlari cloud'a (veya self-host'a) push eder.

Anahtarlar (LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY) yoksa init sessizce
skip eder, agent calismasi ETKILENMEZ. Bu yaklasim Zernio MCP pattern'ini
takip eder (graceful degradation).

Kullanim:
    src/app/api.py lifespan'inde start_langfuse() cagrilir.
    Shutdown'da flush_langfuse() pending span'lari gonderir.
"""
from __future__ import annotations

import logging
import os

from src.app.config import get_settings


log = logging.getLogger(__name__)


_initialized: bool = False


def start_langfuse() -> bool:
    """Langfuse'u baslat. Idempotent — ikinci cagri no-op.

    Returns:
        True if initialization succeeded (or already initialized);
        False if skipped because keys missing or import/connection failed.
    """
    global _initialized
    if _initialized:
        return True

    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.warning(
            "Langfuse anahtarlari yok (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY) "
            "— observability disabled. Agent'lar normal calisir."
        )
        return False

    # Langfuse SDK bu env var'lari okur. Settings'ten al, env'e koy
    # (kullanici .env'de set ettiyse zaten orada — biz override etmeyiz).
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    try:
        from openinference.instrumentation.openai_agents import (
            OpenAIAgentsInstrumentor,
        )
    except ImportError as exc:
        log.warning(
            "openinference-instrumentation-openai-agents import failed: %s "
            "— Langfuse disabled. requirements.txt'i kontrol et.",
            exc,
        )
        return False

    try:
        OpenAIAgentsInstrumentor().instrument()
    except Exception as exc:
        log.warning(
            "Langfuse instrument() failed: %s — observability disabled, "
            "agent'lar normal calisir.",
            exc,
        )
        return False

    _initialized = True
    log.info(
        "Langfuse observability enabled (host=%s, project=*****%s)",
        settings.langfuse_host,
        settings.langfuse_public_key[-4:] if settings.langfuse_public_key else "",
    )
    return True


def flush_langfuse() -> None:
    """Pending span'lari Langfuse'a gonder ve client'i kapat.

    Lifespan shutdown'da cagrilir. Init edilmediyse no-op.
    """
    global _initialized
    if not _initialized:
        return

    try:
        from langfuse import get_client

        client = get_client()
        client.flush()
        log.info("Langfuse flush complete")
    except Exception as exc:
        log.warning("Langfuse flush failed (ignored): %s", exc)
    finally:
        _initialized = False


def is_initialized() -> bool:
    """Test helper — Langfuse aktif mi?"""
    return _initialized


def _reset_for_tests() -> None:
    """Test helper — singleton state'i sifirla."""
    global _initialized
    _initialized = False


__all__ = [
    "start_langfuse",
    "flush_langfuse",
    "is_initialized",
]
