"""Tests for Zernio hosted MCP server entegrasyonu (Faz 1, 2026-05-11)."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.infra.zernio.mcp_server import (
    _ZERNIO_TOOL_ALLOW_PREFIXES,
    _zernio_tool_filter,
    get_zernio_mcp_server,
    reset_zernio_mcp_server,
)


class TestToolFilter:
    """Allow-list semantik kontrolu."""

    @pytest.mark.parametrize("tool_name", [
        # Posts
        "posts_create", "posts_list", "posts_publish_now", "posts_cross_post",
        "posts_retry", "posts_list_failed",
        # Ads
        "list_ad_campaigns", "create_standalone_ad", "boost_post",
        "get_ad_analytics", "search_ad_interests",
        # WhatsApp
        "send_whats_app_bulk", "get_whats_app_contacts",
        "create_whats_app_broadcast", "create_whats_app_template",
        "whatsapp_send", "list_whats_app_templates",
        # Inbox
        "list_inbox_conversations", "send_inbox_message",
        "reply_to_inbox_post", "list_inbox_reviews",
        # Contacts
        "list_contacts", "create_contact", "bulk_create_contacts",
        "set_contact_field_value",
        # Sequences / Broadcasts
        "create_sequence", "enroll_contacts", "pause_sequence",
        "create_broadcast", "send_broadcast",
        # Comment automations
        "create_comment_automation",
        # Analytics
        "get_analytics", "get_best_time_to_post",
        "get_instagram_demographics", "get_you_tube_daily_views",
        # Accounts / Media / Docs
        "accounts_list", "accounts_get",
        "profiles_list",
        "media_generate_upload_link", "media_check_upload_status",
        "docs_search",
    ])
    def test_allowed_tools_pass(self, tool_name):
        assert _zernio_tool_filter(tool_name) is True

    @pytest.mark.parametrize("tool_name", [
        # Yonetim/altyapi — kod tarafinda halledilir, MindBot'a gerek yok
        "create_webhook_settings", "get_webhook_logs", "test_webhook",
        "list_api_keys", "delete_api_key", "create_api_key",
        "get_connect_url", "handle_o_auth_callback",
        "connect_bluesky_credentials",
        "list_account_groups", "create_account_group",
        # Tamamen alakasiz
        "random_xyz", "internal_admin_purge",
    ])
    def test_disallowed_tools_blocked(self, tool_name):
        assert _zernio_tool_filter(tool_name) is False


class TestGetZernioMcpServer:
    """Singleton + lazy init + graceful no-key behavior."""

    def teardown_method(self):
        reset_zernio_mcp_server()

    def test_returns_none_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        assert get_zernio_mcp_server() is None

    def test_returns_server_when_api_key_present(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test_dummy")
        from src.app.config import get_settings
        get_settings.cache_clear()
        server = get_zernio_mcp_server()
        assert server is not None
        # Same instance on subsequent calls (singleton).
        assert get_zernio_mcp_server() is server

    def test_reset_clears_singleton(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_test_dummy")
        from src.app.config import get_settings
        get_settings.cache_clear()
        s1 = get_zernio_mcp_server()
        reset_zernio_mcp_server()
        s2 = get_zernio_mcp_server()
        assert s1 is not s2


class TestRegistryConsistency:
    def test_allow_prefixes_non_empty(self):
        assert len(_ZERNIO_TOOL_ALLOW_PREFIXES) >= 30
        assert all(isinstance(p, str) and p for p in _ZERNIO_TOOL_ALLOW_PREFIXES)


class TestAgentWiring:
    """3 agent factory de MCP server'i (varsa) Agent'a baglar."""

    def teardown_method(self):
        reset_zernio_mcp_server()

    def _stub_mcp(self, monkeypatch):
        """Agent factory'lerin gercek MCP server kurmasini engelle —
        sadece 'baglandi mi' davranisini test ediyoruz."""
        sentinel = object()
        monkeypatch.setattr(
            "src.infra.zernio.mcp_server.get_zernio_mcp_server",
            lambda: sentinel,
        )
        return sentinel

    def test_orchestrator_attaches_mcp_when_available(self, monkeypatch):
        sentinel = self._stub_mcp(monkeypatch)
        from src.agents.orchestrator_agent import create_orchestrator_agent
        agent = create_orchestrator_agent()
        assert sentinel in agent.mcp_servers

    def test_orchestrator_omits_mcp_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "src.infra.zernio.mcp_server.get_zernio_mcp_server",
            lambda: None,
        )
        from src.agents.orchestrator_agent import create_orchestrator_agent
        agent = create_orchestrator_agent()
        assert agent.mcp_servers == []

    def test_sales_analyst_attaches_mcp(self, monkeypatch):
        sentinel = self._stub_mcp(monkeypatch)
        from src.agents.sales.sales_analyst_agent import create_sales_analyst_agent
        agent = create_sales_analyst_agent()
        assert sentinel in agent.mcp_servers

    def test_marketing_attaches_mcp(self, monkeypatch):
        sentinel = self._stub_mcp(monkeypatch)
        from src.agents.marketing_agent import create_marketing_agent
        agent = create_marketing_agent()
        assert sentinel in agent.mcp_servers
