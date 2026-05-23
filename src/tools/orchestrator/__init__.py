"""Orchestrator tools package — platform-specific posting, storage, and firestore tools."""

from agents import FunctionTool

from .storage import upload_file, list_files, delete_file
from .firestore import get_document, save_document, query_documents
from .instagram import post_on_instagram, post_carousel_on_instagram
from .tiktok import post_carousel_on_tiktok, post_on_tiktok
from .linkedin import post_on_linkedin, post_carousel_on_linkedin
from .youtube import post_on_youtube
from .business import fetch_business, report_error
from src.tools.n8n_bridge_tools import get_n8n_bridge_tools


def get_orchestrator_tools() -> list[FunctionTool]:
    """Return the list of tools for the orchestrator agent.

    Posting tool'lar (post_on_instagram vb.) BILEREK HARIC tutuldu —
    Şef post atmaz, marketing/video agent'lara delege eder. Defense-in-depth:
    instructions yasaklasa bile dosya erişimi de olmasın.
    """
    return [
        upload_file,
        list_files,
        delete_file,
        get_document,
        save_document,
        query_documents,
        report_error,
        *get_n8n_bridge_tools(),  # Adim 9: n8n köprüsü (list/call/health)
    ]


__all__ = [
    "upload_file",
    "list_files",
    "delete_file",
    "get_document",
    "save_document",
    "query_documents",
    "post_on_instagram",
    "post_carousel_on_instagram",
    "post_on_youtube",
    "post_carousel_on_tiktok",
    "post_on_tiktok",
    "post_on_linkedin",
    "post_carousel_on_linkedin",
    "report_error",
    "get_orchestrator_tools",
    "fetch_business",
]
