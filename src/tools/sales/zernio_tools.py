"""Zernio (WhatsApp + Inbox) tools for the Sales agents.

Adim 2 of the Sales roadmap: 4 read/write tools that wrap the
``ZernioClient``. These tools are infrastructure-only at this point — they
are NOT bound to any agent yet (per CLAUDE.md rule #7). Adim 4 (Outreach
Agent) and Adim 5 (Webhook Listener) will register them.

Contract:
- Each tool returns a structured dict with ``success: bool``.
- Errors are routed through ``classify_error(exc, "zernio")`` so the agent
  can read ``error_code`` / ``retryable`` / ``user_message_tr``.
"""
from __future__ import annotations

from typing import Any

from agents import function_tool

from src.infra.errors import ErrorCode, classify_error


# ---------------------------------------------------------------------------
# Client resolver (patched in tests)
# ---------------------------------------------------------------------------


def _get_client():
    """Indirection so tests can swap in a fake without touching settings."""
    from src.infra.zernio import get_zernio_client

    return get_zernio_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MAX_LIMIT = 100


def _clamp(limit: int, lo: int = 1, hi: int = _MAX_LIMIT) -> int:
    return max(lo, min(limit, hi))


def _normalise_phone(phone: str) -> str:
    """Strip whitespace and ensure leading ``+``.

    Zernio stores numbers in E.164 (``+90...``) but callers may pass them
    without the plus sign.
    """
    phone = (phone or "").strip().replace(" ", "")
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    return phone


def _invalid_input(message_tr: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "error_code": ErrorCode.INVALID_INPUT.value,
        "service": "zernio",
        "retryable": False,
        "user_message_tr": message_tr,
    }


def _not_found(message_tr: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "error_code": ErrorCode.NOT_FOUND.value,
        "service": "zernio",
        "retryable": False,
        "user_message_tr": message_tr,
    }


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


async def _list_contacts_impl(limit: int = 100, skip: int = 0) -> dict[str, Any]:
    """Paginate WhatsApp contacts for the configured account."""
    try:
        client = _get_client()
        data = await client.list_contacts(limit=_clamp(limit), skip=max(0, skip))
        contacts = data.get("contacts", [])
        return {
            "success": True,
            "contacts": contacts,
            "count": len(contacts),
            "total": data.get("total"),
            "next_skip": skip + len(contacts) if contacts else None,
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _find_conversation_impl(phone: str) -> dict[str, Any]:
    """Locate the conversation thread for a phone number.

    Zernio's conversation list does not expose a direct phone filter, so we
    fetch up to ``_MAX_LIMIT`` and match locally. Good enough for the
    Slowdays workload (a few hundred active threads); revisit if it grows.
    """
    normalized = _normalise_phone(phone)
    if not normalized:
        return _invalid_input(
            "Telefon numarasi bos olamaz.", "phone is required"
        )
    try:
        client = _get_client()
        data = await client.list_conversations(limit=_MAX_LIMIT)
        for conv in data.get("conversations", []):
            contact = conv.get("contact") or {}
            conv_phone = _normalise_phone(contact.get("phone", ""))
            if conv_phone and conv_phone == normalized:
                return {
                    "success": True,
                    "conversation_id": conv.get("id"),
                    "conversation": conv,
                }
        return _not_found(
            "Bu numaraya ait konusma bulunamadi.",
            f"no conversation for {normalized}",
        )
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _send_message_impl(conversation_id: str, message: str) -> dict[str, Any]:
    """Free-form WhatsApp reply on an existing thread (24h window only)."""
    if not (message and message.strip()):
        return _invalid_input(
            "Bos mesaj gonderilemez.", "message is empty"
        )
    if not conversation_id:
        return _invalid_input(
            "conversation_id zorunlu.", "conversation_id is required"
        )
    try:
        client = _get_client()
        data = await client.send_message(conversation_id, message)
        return {
            "success": True,
            "message_id": data.get("messageId") or data.get("id"),
            "raw": data,
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _send_whatsapp_template_impl(
    phone: str,
    template_name: str,
    variables: list[str] | None = None,
    language: str = "tr",
) -> dict[str, Any]:
    """Send a Meta-approved WhatsApp template (cold outreach via /whatsapp/bulk).

    Unlike ``send_message`` (free-form, 24h window), templates can initiate
    conversations. Slowdays kampanyasi: ``ege_otel_yaz_sezon_v1`` template,
    ``variables=[otel_adi]``.
    """
    if not phone or not phone.strip():
        return _invalid_input(
            "Telefon numarasi gerekli.", "phone is required"
        )
    if not template_name or not template_name.strip():
        return _invalid_input(
            "template_name gerekli.", "template_name is required"
        )
    try:
        client = _get_client()
        data = await client.send_template(
            phone=phone.strip(),
            template_name=template_name.strip(),
            variables=variables or [],
            language=language,
        )
        return {
            "success": True,
            "phone": phone.strip(),
            "template": template_name,
            "raw": data,
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


async def _tag_contact_impl(contact_id: str, tags: list[str]) -> dict[str, Any]:
    """Replace tag set on a Zernio contact (CRM segmentation)."""
    if not contact_id:
        return _invalid_input(
            "contact_id zorunlu.", "contact_id is required"
        )
    if not tags:
        return _invalid_input(
            "En az bir etiket gerekli.", "tags must be a non-empty list"
        )
    try:
        client = _get_client()
        data = await client.tag_contact(contact_id, tags)
        return {
            "success": True,
            "contact_id": data.get("id") or contact_id,
            "tags": data.get("tags", tags),
        }
    except Exception as exc:
        return classify_error(exc, "zernio")


# ---------------------------------------------------------------------------
# function_tool wrappers
# ---------------------------------------------------------------------------


list_contacts = function_tool(
    name_override="list_contacts",
    description_override=(
        "List Zernio WhatsApp contacts (paginated). Args: limit (1-100, default 100), "
        "skip (default 0). Returns {success, contacts, count, total, next_skip}."
    ),
    strict_mode=False,
)(_list_contacts_impl)


find_conversation = function_tool(
    name_override="find_conversation",
    description_override=(
        "Find an active Zernio inbox conversation by phone number (E.164 with or "
        "without leading +). Returns {success, conversation_id, conversation} or "
        "NOT_FOUND structured error."
    ),
    strict_mode=False,
)(_find_conversation_impl)


send_message = function_tool(
    name_override="send_message",
    description_override=(
        "Send a free-form WhatsApp reply to an existing conversation. "
        "Args: conversation_id (required), message (non-empty). Only valid in the "
        "24h customer-service window — outside it Zernio returns a 4xx and the "
        "caller must use a template instead."
    ),
    strict_mode=False,
)(_send_message_impl)


send_whatsapp_template = function_tool(
    name_override="send_whatsapp_template",
    description_override=(
        "Send a Meta-approved WhatsApp template message via Zernio /whatsapp/bulk. "
        "Used for cold outreach — initiates conversations outside the 24h CS window. "
        "Args: phone (E.164), template_name (Meta-approved), variables (list[str], "
        "ordered by template body), language (default 'tr'). Slowdays kampanyasi "
        "ornek: phone='+90...', template_name='ege_otel_yaz_sezon_v1', "
        "variables=['Otel Adi']."
    ),
    strict_mode=False,
)(_send_whatsapp_template_impl)


tag_contact = function_tool(
    name_override="tag_contact",
    description_override=(
        "Replace the tag set on a Zernio contact (full overwrite, not merge). "
        "Args: contact_id, tags (non-empty list). CRM segments: hot_lead, "
        "warm_lead, cold_lead, oto_yanit_gonderildi, bolge_*, butce_*, ..."
    ),
    strict_mode=False,
)(_tag_contact_impl)


def get_zernio_tools() -> list:
    """All Zernio WhatsApp/Inbox tools (Outreach + Webhook agents will use)."""
    return [list_contacts, find_conversation, send_message, send_whatsapp_template, tag_contact]


__all__ = [
    "list_contacts",
    "find_conversation",
    "send_message",
    "send_whatsapp_template",
    "tag_contact",
    "get_zernio_tools",
    # Exposed for direct testing
    "_list_contacts_impl",
    "_find_conversation_impl",
    "_send_message_impl",
    "_send_whatsapp_template_impl",
    "_tag_contact_impl",
    "_get_client",
]
