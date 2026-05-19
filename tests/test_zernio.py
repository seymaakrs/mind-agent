"""Tests for Zernio client + sales tools.

Zernio is the WhatsApp/Inbox/Social aggregator (https://api.zernio.com/v1) used
in the Slowdays cold outreach campaign. This test file covers:

- HTTP client (`src/infra/zernio/`) — request shape, auth, status handling
- 4 tool wrappers (`src/tools/sales/zernio_tools.py`) — happy path + error
  classification (structured dict contract)
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# OPENAI_API_KEY is read at module import in agents-sdk; provide a stub.
os.environ.setdefault("OPENAI_API_KEY", "test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status: int, json_body: Any = None, text_body: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text_body or (str(json_body) if json_body else "")
    resp.json = MagicMock(return_value=json_body if json_body is not None else {})
    return resp


def _patch_async_client(method: str, response: MagicMock):
    """Patch httpx.AsyncClient.<method> to return `response`."""
    return patch.object(
        httpx.AsyncClient,
        method,
        new=AsyncMock(return_value=response),
    )


# ---------------------------------------------------------------------------
# ZernioClient — HTTP layer
# ---------------------------------------------------------------------------


class TestZernioClient:
    def _client(self):
        from src.infra.zernio import ZernioClient

        return ZernioClient(
            api_key="sk_test_123",
            account_id="wa_acc_id",
            base_url="https://api.zernio.com/v1",
        )

    @pytest.mark.asyncio
    async def test_list_contacts_uses_account_id_and_pagination(self):
        client = self._client()
        with _patch_async_client(
            "get", _mock_response(200, {"contacts": [{"id": "c1"}], "total": 1})
        ) as mock_get:
            result = await client.list_contacts(limit=50, skip=10)

        assert result["contacts"] == [{"id": "c1"}]
        kwargs = mock_get.await_args.kwargs
        params = kwargs["params"]
        assert params["accountId"] == "wa_acc_id"
        assert params["limit"] == 50
        assert params["skip"] == 10
        url = mock_get.await_args.args[0]
        assert url.endswith("/whatsapp/contacts")

    @pytest.mark.asyncio
    async def test_list_conversations_filters_by_account(self):
        client = self._client()
        with _patch_async_client(
            "get",
            _mock_response(200, {"conversations": [{"id": "conv1", "phone": "+90..."}]}),
        ) as mock_get:
            await client.list_conversations(limit=100)

        params = mock_get.await_args.kwargs["params"]
        assert params["accountId"] == "wa_acc_id"
        assert params["limit"] == 100
        url = mock_get.await_args.args[0]
        assert url.endswith("/inbox/conversations")

    @pytest.mark.asyncio
    async def test_send_message_posts_account_and_message(self):
        client = self._client()
        with _patch_async_client(
            "post", _mock_response(200, {"messageId": "m-1", "ok": True})
        ) as mock_post:
            result = await client.send_message("conv-99", "Merhaba")

        assert result["messageId"] == "m-1"
        url = mock_post.await_args.args[0]
        assert url.endswith("/inbox/conversations/conv-99/messages")
        body = mock_post.await_args.kwargs["json"]
        assert body == {"accountId": "wa_acc_id", "message": "Merhaba"}

    @pytest.mark.asyncio
    async def test_tag_contact_patches_tags(self):
        client = self._client()
        with _patch_async_client(
            "patch", _mock_response(200, {"id": "c-1", "tags": ["hot_lead"]})
        ) as mock_patch:
            result = await client.tag_contact("c-1", ["hot_lead", "yaniti_var"])

        assert result["tags"] == ["hot_lead"]
        url = mock_patch.await_args.args[0]
        assert url.endswith("/contacts/c-1")
        body = mock_patch.await_args.kwargs["json"]
        assert body == {"tags": ["hot_lead", "yaniti_var"]}

    @pytest.mark.asyncio
    async def test_auth_header_uses_bearer(self):
        client = self._client()
        with _patch_async_client("get", _mock_response(200, {"contacts": []})) as mock_get:
            await client.list_contacts()
        headers = mock_get.await_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk_test_123"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_4xx_raises_service_error(self):
        from src.infra.errors import ServiceError

        client = self._client()
        with _patch_async_client(
            "get", _mock_response(401, text_body="Unauthorized")
        ):
            with pytest.raises(ServiceError) as excinfo:
                await client.list_contacts()
        assert excinfo.value.status_code == 401
        assert excinfo.value.service == "zernio"


class TestGetZernioClient:
    def test_factory_uses_settings(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_API_KEY", "sk_xx")
        monkeypatch.setenv("ZERNIO_BASE_URL", "https://api.zernio.com/v1")
        monkeypatch.setenv("ZERNIO_WA_ACCOUNT_ID", "wa-default")
        from src.app.config import get_settings

        get_settings.cache_clear()
        from src.infra.zernio import get_zernio_client

        client = get_zernio_client()
        assert client.api_key == "sk_xx"
        assert client.account_id == "wa-default"
        assert client.base_url == "https://api.zernio.com/v1"

    def test_factory_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
        from src.app.config import get_settings

        get_settings.cache_clear()
        from src.infra.zernio import get_zernio_client

        with pytest.raises(ValueError, match="ZERNIO_API_KEY"):
            get_zernio_client()


# ---------------------------------------------------------------------------
# Tool wrappers — structured dict contract
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_zernio_client():
    """Async-capable mock of ZernioClient."""
    client = MagicMock()
    client.list_contacts = AsyncMock()
    client.list_conversations = AsyncMock()
    client.send_message = AsyncMock()
    client.tag_contact = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _patch_factory(monkeypatch, fake_zernio_client):
    """Inject the fake client wherever zernio_tools resolves it."""
    from src.tools.sales import zernio_tools as zt

    monkeypatch.setattr(zt, "_get_client", lambda: fake_zernio_client)
    yield


class TestListContactsTool:
    @pytest.mark.asyncio
    async def test_returns_structured_success(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _list_contacts_impl

        fake_zernio_client.list_contacts.return_value = {
            "contacts": [{"id": "c1"}, {"id": "c2"}],
            "total": 2,
        }
        result = await _list_contacts_impl(limit=50, skip=0)
        assert result["success"] is True
        assert len(result["contacts"]) == 2
        fake_zernio_client.list_contacts.assert_awaited_once_with(limit=50, skip=0)

    @pytest.mark.asyncio
    async def test_clamps_limit(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _list_contacts_impl

        fake_zernio_client.list_contacts.return_value = {"contacts": []}
        await _list_contacts_impl(limit=999)
        kwargs = fake_zernio_client.list_contacts.await_args.kwargs
        assert kwargs["limit"] <= 100

    @pytest.mark.asyncio
    async def test_classifies_service_error(self, fake_zernio_client):
        from src.infra.errors import ServiceError
        from src.tools.sales.zernio_tools import _list_contacts_impl

        fake_zernio_client.list_contacts.side_effect = ServiceError(
            "boom", status_code=429, service="zernio"
        )
        result = await _list_contacts_impl()
        assert result["success"] is False
        assert result["error_code"] == "RATE_LIMIT"
        assert result["service"] == "zernio"


class TestFindConversationTool:
    @pytest.mark.asyncio
    async def test_finds_by_phone(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _find_conversation_impl

        fake_zernio_client.list_conversations.return_value = {
            "conversations": [
                {"id": "conv-1", "contact": {"phone": "+905551234567"}},
                {"id": "conv-2", "contact": {"phone": "+905559999999"}},
            ]
        }
        result = await _find_conversation_impl(phone="+905551234567")
        assert result["success"] is True
        assert result["conversation_id"] == "conv-1"

    @pytest.mark.asyncio
    async def test_normalises_phone_with_or_without_plus(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _find_conversation_impl

        fake_zernio_client.list_conversations.return_value = {
            "conversations": [{"id": "conv-1", "contact": {"phone": "+905551234567"}}]
        }
        result = await _find_conversation_impl(phone="905551234567")
        assert result["success"] is True
        assert result["conversation_id"] == "conv-1"

    @pytest.mark.asyncio
    async def test_returns_not_found_when_no_match(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _find_conversation_impl

        fake_zernio_client.list_conversations.return_value = {"conversations": []}
        result = await _find_conversation_impl(phone="+905550000000")
        assert result["success"] is False
        assert result["error_code"] == "NOT_FOUND"


class TestSendMessageTool:
    @pytest.mark.asyncio
    async def test_sends_free_form_text(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _send_message_impl

        fake_zernio_client.send_message.return_value = {"messageId": "m-1"}
        result = await _send_message_impl(conversation_id="conv-1", message="Selam")
        assert result["success"] is True
        assert result["message_id"] == "m-1"
        fake_zernio_client.send_message.assert_awaited_once_with("conv-1", "Selam")

    @pytest.mark.asyncio
    async def test_rejects_empty_message(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _send_message_impl

        result = await _send_message_impl(conversation_id="conv-1", message="   ")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"
        fake_zernio_client.send_message.assert_not_awaited()


class TestTagContactTool:
    @pytest.mark.asyncio
    async def test_patches_tags(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _tag_contact_impl

        fake_zernio_client.tag_contact.return_value = {
            "id": "c1",
            "tags": ["hot_lead", "yaniti_var"],
        }
        result = await _tag_contact_impl(contact_id="c1", tags=["hot_lead", "yaniti_var"])
        assert result["success"] is True
        assert "hot_lead" in result["tags"]

    @pytest.mark.asyncio
    async def test_rejects_empty_tag_list(self, fake_zernio_client):
        from src.tools.sales.zernio_tools import _tag_contact_impl

        result = await _tag_contact_impl(contact_id="c1", tags=[])
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Tool registration — exposed names + function_tool wrapping
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_get_zernio_tools_exposes_five(self):
        from src.tools.sales.zernio_tools import get_zernio_tools

        tools = get_zernio_tools()
        names = {t.name for t in tools}
        assert names == {
            "list_contacts",
            "find_conversation",
            "send_message",
            "send_whatsapp_template",
            "tag_contact",
        }
