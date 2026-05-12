"""Zernio hosted MCP server entegrasyonu (Sema'nin onerisi, 2026-05-11).

Zernio'nun resmi MCP server'i (https://mcp.zernio.com/mcp) 280+ tool'u
otomatik expose ediyor: ads, posts, inbox, analytics, sequences, broadcasts,
comment automations, WhatsApp flows/templates/groups, vb.

Mind-agent'in worker'lari (Outreach, Auto-reply) hala low-level Python
client kullanir (deterministic, hizli). MindBot orchestrator + Sales
Analyst + Marketing Agent ise bu MCP'ye baglanir — kullanici dogal dilde
"reklamlarimi listele", "haftalik IG analytics", "Twitter'a su mesaji at"
diye konusabilir, MCP otomatik tool secimi yapar.

Singleton pattern: tek bir MCPServerStreamableHttp instance her agent
factory tarafindan paylasilir. Lazy-init (ilk agent create'inde
acilir), cache_tools_list=True (her cagri 280 tool listesi cekmesin).

Tool filter:
- 280+ tool LLM context'ini sismez sekilde ~80 alakali tool'a kisitlanir
- Worker tarafinda yapilan dusuk-seviyeli WhatsApp send/contacts tool'lari
  MCP'den de gelir ama isim catismasi yok (MCP toolname snake_case
  prefix'li: ``send_inbox_message``, bizimkiler tool wrap ile farkli ad).
"""
from __future__ import annotations

import logging
from typing import Any

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from src.app.config import get_settings


log = logging.getLogger(__name__)


# Allow-list: tool isminin BU prefix'lerden biriyle ESLESMESI yeterli.
# 280+ Zernio tool icinden ~80 alakali olani — Slowdays + Beyza B2B
# kullanim senaryolari icin secildi. Geri kalanlar (webhooks_*, api_keys_*,
# connect_*, account_groups_*) MindBot'tan ulasilmaz; kod tarafinda yonetilir.
_ZERNIO_TOOL_ALLOW_PREFIXES: tuple[str, ...] = (
    # Posts (yayin yonetimi - Marketing Agent + MindBot)
    "posts_",
    # Ads (Slowdays Meta reklam — Sema senaryolari)
    "ads_",
    "list_ad_",
    "create_standalone_ad",
    "boost_post",
    "get_ad_",
    "search_ad_",
    # WhatsApp (Slowdays + Beyza)
    "whatsapp_",
    "send_whats_app_",
    "get_whats_app_",
    "create_whats_app_",
    "list_whats_app_",
    # Inbox (mesaj/comment/review)
    "inbox_",
    "list_inbox_",
    "send_inbox_",
    "reply_to_inbox_",
    # Contacts (CRM yedek)
    "contacts_",
    "list_contacts",
    "create_contact",
    "bulk_create_contacts",
    "set_contact_field_value",
    # Sequences (drip kampanya)
    "sequences_",
    "create_sequence",
    "enroll_contacts",
    "activate_sequence",
    "pause_sequence",
    # Broadcasts
    "broadcasts_",
    "create_broadcast",
    "schedule_broadcast",
    "send_broadcast",
    # Comment Automations
    "comment_automations_",
    "create_comment_automation",
    # Analytics
    "analytics_",
    "get_analytics",
    "get_best_time_to_post",
    "get_instagram_",
    "get_you_tube_",
    "get_googlebusiness_",
    # Accounts (read-only profile)
    "accounts_list",
    "accounts_get",
    # Profiles (multi-client)
    "profiles_list",
    "profiles_get",
    # Media (image/video upload flow)
    "media_generate_upload_link",
    "media_check_upload_status",
    # Docs (Zernio API dokumentasyon arama)
    "docs_search",
)


def _zernio_tool_filter(tool_name: str) -> bool:
    """Tool allow-list check. Filter fonksiyonu MCPServerStreamableHttp'a
    static callable olarak verilir (SDK her tool icin sorar)."""
    return any(tool_name.startswith(p) or tool_name == p.rstrip("_")
               for p in _ZERNIO_TOOL_ALLOW_PREFIXES)


_singleton: MCPServerStreamableHttp | None = None
_active_servers: list = []          # FastAPI lifespan ile connected olanlar


def get_zernio_mcp_server() -> MCPServerStreamableHttp | None:
    """Singleton MCP server. ``ZERNIO_API_KEY`` set degilse None doner ve
    agent factory'ler MCP'siz devam eder (graceful degradation)."""
    global _singleton
    if _singleton is not None:
        return _singleton

    settings = get_settings()
    api_key = settings.zernio_api_key
    if not api_key:
        log.warning(
            "ZERNIO_API_KEY not configured — Zernio MCP server disabled "
            "(MindBot won't have access to Zernio's 280+ tools)"
        )
        return None

    _singleton = MCPServerStreamableHttp(
        params=MCPServerStreamableHttpParams(
            url="https://mcp.zernio.com/mcp",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        ),
        cache_tools_list=True,         # tool listesi nadiren degisir
        name="zernio",
        client_session_timeout_seconds=30.0,
        tool_filter=_zernio_tool_filter,
        max_retry_attempts=2,
        retry_backoff_seconds_base=1.0,
    )
    return _singleton


def reset_zernio_mcp_server() -> None:
    """Test helper — singleton'i sifirla."""
    global _singleton, _active_servers
    _singleton = None
    _active_servers = []


async def start_mcp_servers() -> None:
    """FastAPI lifespan **startup** hook: MCP server'lari connect et.

    SDK 0.6.2'de Agent(mcp_servers=[...]) OTOMATIK connect etmiyor.
    SDK'da MCPServerManager bazi sub-version'larda yok — biz minimal
    manager'imizi inline yaziyoruz (server.connect() / server.cleanup()
    direkt cagrilarak). Basarisiz olanlar discard edilir, agent yine
    calisir (graceful degradation).
    """
    global _active_servers
    zernio = get_zernio_mcp_server()
    if not zernio:
        log.info("No Zernio MCP server to start (ZERNIO_API_KEY missing)")
        _active_servers = []
        return

    candidates = [zernio]
    connected: list = []
    for server in candidates:
        name = getattr(server, "name", type(server).__name__)
        try:
            await server.connect()
            connected.append(server)
            log.info("MCP server connected: %s", name)
        except Exception as exc:
            log.warning(
                "MCP server connect failed: %s (%s) — skipping, agent will run without it",
                name, exc,
            )
    _active_servers = connected
    log.info(
        "MCP startup complete: %d/%d active server(s)",
        len(connected), len(candidates),
    )


async def stop_mcp_servers() -> None:
    """FastAPI lifespan **shutdown** hook: MCP cleanup."""
    global _active_servers
    for server in _active_servers:
        try:
            await server.cleanup()
        except Exception as exc:
            log.warning("MCP cleanup error (ignored): %s", exc)
    _active_servers = []


def get_active_mcp_servers() -> list:
    """Agent factory'ler bunu cagirir; lifespan'de connect edilmis olanlari doner.

    Bos liste donerse agent MCP'siz devam eder (Zernio yok ama orchestrator
    diger tool'lari yine kullanabilir).
    """
    return list(_active_servers)


__all__ = [
    "get_zernio_mcp_server",
    "get_active_mcp_servers",
    "start_mcp_servers",
    "stop_mcp_servers",
    "reset_zernio_mcp_server",
    "_zernio_tool_filter",
    "_ZERNIO_TOOL_ALLOW_PREFIXES",
]
