"""n8n köprü tool'lari — MindBot orchestrator'inin n8n.cloud'a HTTP üzerinden
ulasmasini saglar.

Üc tool:
- ``list_n8n_workflows`` (read-only): registry'deki bilinen workflowlari döner.
- ``call_n8n_workflow``: ad ile workflow webhook'una POST/GET atar.
- ``n8n_workflow_health``: registry meta + (opsiyonel) son execution durumu
  (su an sadece registry; future: n8n REST API ile gercek execution log).

n8n base URL: ``N8N_BASE_URL`` env (örnek: ``https://mindidai.app.n8n.cloud``).
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from agents import function_tool

from src.infra.errors import classify_error
from src.tools.n8n_registry import N8N_REGISTRY, find_workflow


_TIMEOUT_SECONDS = 30.0
_INVALID = "INVALID_INPUT"


def _base_url() -> str | None:
    return os.environ.get("N8N_BASE_URL") or None


def _missing_base_url() -> dict[str, Any]:
    return {
        "success": False,
        "error_code": _INVALID,
        "error": "N8N_BASE_URL env not configured.",
        "user_message_tr": (
            "n8n base URL ayarli degil. Mind-agent Cloud Run env'ine "
            "`N8N_BASE_URL` eklenmeli."
        ),
    }


async def _list_n8n_workflows_impl() -> dict[str, Any]:
    """Registry'deki bilinen n8n workflow'larini döner. Argumansiz."""
    items = [
        {
            "name": wf.name,
            "workflow_id": wf.workflow_id,
            "webhook_path": wf.webhook_path,
            "http_method": wf.http_method,
            "description": wf.description,
        }
        for wf in N8N_REGISTRY
    ]
    return {
        "success": True,
        "count": len(items),
        "workflows": items,
        "summary_tr": (
            f"n8n'de bilinen {len(items)} workflow var "
            f"(Drive/Sheets/Docs + Itiraz/Lead Toplama/Bekci Alert vb.). "
            "Detay icin call_n8n_workflow kullan."
        ),
    }


async def _call_n8n_workflow_impl(
    name: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Bilinen bir n8n workflow'unu webhook üzerinden tetikler.

    Args:
        name: registry name (örn. 'drive_upload', 'itiraz_agent')
        body: workflow'un bekledigi JSON payload (opsiyonel)
    """
    if not name or not name.strip():
        return {
            "success": False,
            "error_code": _INVALID,
            "error": "workflow name is required",
            "user_message_tr": "n8n workflow adi gerekli.",
        }
    wf = find_workflow(name)
    if not wf:
        known = ", ".join(w.name for w in N8N_REGISTRY)
        return {
            "success": False,
            "error_code": "NOT_FOUND",
            "error": f"unknown workflow: {name}",
            "user_message_tr": (
                f"'{name}' n8n registry'de yok. Bilinen workflow'lar: {known}."
            ),
        }
    base = _base_url()
    if not base:
        return _missing_base_url()

    url = f"{base.rstrip('/')}/webhook/{wf.webhook_path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            if wf.http_method.upper() == "GET":
                response = await client.get(url, params=body or {})
            else:
                response = await client.post(url, json=body or {})
        if response.status_code >= 400:
            return {
                "success": False,
                "error_code": "UPSTREAM",
                "status_code": response.status_code,
                "error": response.text[:500],
                "user_message_tr": (
                    f"n8n '{wf.name}' workflow'u hata dondurdu "
                    f"({response.status_code})."
                ),
            }
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:1000]}
        return {
            "success": True,
            "workflow": wf.name,
            "status_code": response.status_code,
            "data": data,
            "summary_tr": f"n8n '{wf.name}' workflow'u tetiklendi.",
        }
    except Exception as exc:
        return classify_error(exc, "n8n")


async def _n8n_workflow_health_impl(name: str) -> dict[str, Any]:
    """Registry meta'sini döner. (n8n REST API ile gercek execution health
    sonraki adimda eklenecek — su an sadece konfigure mi diye bakar.)"""
    if not name or not name.strip():
        return {
            "success": False,
            "error_code": _INVALID,
            "user_message_tr": "Workflow adi gerekli.",
        }
    wf = find_workflow(name)
    if not wf:
        return {
            "success": False,
            "error_code": "NOT_FOUND",
            "user_message_tr": f"'{name}' n8n registry'de yok.",
        }
    base = _base_url()
    configured = bool(base and wf.workflow_id)
    return {
        "success": True,
        "name": wf.name,
        "workflow_id": wf.workflow_id or None,
        "webhook_path": wf.webhook_path,
        "configured": configured,
        "description": wf.description,
        "summary_tr": (
            f"n8n '{wf.name}' workflow'u "
            f"{'configure edilmis' if configured else 'KONFIGURASYON EKSIK'}."
        ),
    }


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


list_n8n_workflows = function_tool(
    name_override="list_n8n_workflows",
    description_override=(
        "n8n'de bilinen tum workflow'lari listele (Drive/Sheets/Docs, "
        "Itiraz, Lead Toplama, Bekci Alert, vb.). Argumansiz. Kullanici "
        "'n8n'de neler var', 'hangi otomasyonlari kullanabilirim' diye "
        "sorarsa bu tool."
    ),
    strict_mode=False,
)(_list_n8n_workflows_impl)


call_n8n_workflow = function_tool(
    name_override="call_n8n_workflow",
    description_override=(
        "Bilinen bir n8n workflow'unu webhook ile tetikler. "
        "Args: name (registry'deki ad, ornek 'drive_upload', 'itiraz_agent', "
        "'sheets_append'), body (workflow'un bekledigi JSON, opsiyonel). "
        "Drive/Sheets/Docs islemleri, Itiraz handler, Lead toplama webhook "
        "tetikleme gibi seyler icin."
    ),
    strict_mode=False,
)(_call_n8n_workflow_impl)


n8n_workflow_health = function_tool(
    name_override="n8n_workflow_health",
    description_override=(
        "Belirli bir n8n workflow'unun durumu: configure edilmis mi, ne "
        "yapiyor, ID'si ne. Args: name. Kullanici 'X workflow calisiyor mu' "
        "diye sorarsa."
    ),
    strict_mode=False,
)(_n8n_workflow_health_impl)


def get_n8n_bridge_tools() -> list:
    return [list_n8n_workflows, call_n8n_workflow, n8n_workflow_health]


__all__ = [
    "list_n8n_workflows",
    "call_n8n_workflow",
    "n8n_workflow_health",
    "get_n8n_bridge_tools",
    "_list_n8n_workflows_impl",
    "_call_n8n_workflow_impl",
    "_n8n_workflow_health_impl",
]
