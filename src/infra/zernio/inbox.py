"""Inbox endpoints on Zernio (conversations + free-form replies)."""
from __future__ import annotations

from typing import Any


class _InboxMixin:
    """``/inbox/conversations`` operations.

    NOTE: This mixin sends *free-form* messages only. Cold outreach uses
    template-based ``/whatsapp/bulk`` which lives in a separate tool (Adim 4
    — Outreach Agent).
    """

    async def list_conversations(self, limit: int = 100) -> dict[str, Any]:
        """Active conversations for this account (paginated by limit)."""
        params = {"accountId": self.account_id, "limit": limit}
        return await self._get("/inbox/conversations", params=params)

    async def find_conversation_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Match a conversation by ``contact.phone`` (digits-only compare).

        Zernio's conversation list has no server-side phone filter, so we
        page up to 200 and match locally. Returns None when not found.
        """
        digits = "".join(ch for ch in (phone or "") if ch.isdigit())
        if not digits:
            return None
        data = await self.list_conversations(limit=200)
        for conv in data.get("conversations", []) or []:
            contact = conv.get("contact") or {}
            conv_digits = "".join(ch for ch in str(contact.get("phone", "")) if ch.isdigit())
            if conv_digits and conv_digits == digits:
                return conv
        return None

    async def send_message(self, conversation_id: str, message: str) -> dict[str, Any]:
        """Free-form text reply on an existing conversation.

        WhatsApp policy note: free-form messages are only allowed inside the
        24h customer service window. Outside that window Zernio rejects with
        a 4xx; callers should fall back to a template via the future bulk
        tool.
        """
        body = {"accountId": self.account_id, "message": message}
        return await self._post(f"/inbox/conversations/{conversation_id}/messages", json=body)
