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

    async def send_message(self, conversation_id: str, message: str) -> dict[str, Any]:
        """Free-form text reply on an existing conversation.

        WhatsApp policy note: free-form messages are only allowed inside the
        24h customer service window. Outside that window Zernio rejects with
        a 4xx; callers should fall back to a template via the future bulk
        tool.
        """
        body = {"accountId": self.account_id, "message": message}
        return await self._post(f"/inbox/conversations/{conversation_id}/messages", json=body)
