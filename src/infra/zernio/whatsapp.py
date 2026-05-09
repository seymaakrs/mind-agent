"""WhatsApp endpoints on Zernio (contacts + tagging)."""
from __future__ import annotations

from typing import Any


class _WhatsAppMixin:
    """``/whatsapp/contacts`` and ``/contacts/{id}`` (tagging) operations."""

    async def list_contacts(self, limit: int = 100, skip: int = 0) -> dict[str, Any]:
        """Paginated WhatsApp contact list for this account.

        Zernio enforces ``accountId`` on this endpoint; the client always
        injects ``self.account_id`` so callers cannot accidentally cross
        accounts.
        """
        params = {
            "accountId": self.account_id,
            "limit": limit,
            "skip": skip,
        }
        return await self._get("/whatsapp/contacts", params=params)

    async def tag_contact(self, contact_id: str, tags: list[str]) -> dict[str, Any]:
        """Replace the contact's tag set (Zernio does a full replace, not merge).

        Beyza's CRM segmentation tags live here: ``hot_lead``,
        ``oto_yanit_gonderildi``, ``bolge_bodrum``, ...
        """
        return await self._patch(f"/contacts/{contact_id}", json={"tags": tags})
