"""n8n workflow registry — MindBot bilinen n8n iş akislarini buradan tetikler.

Hibrit mimari karari (2026-05-11):
- IÇERIK üretimi (Instagram/Image/Video/Analysis) mind-agent'tan yapilir.
- Drive/Sheets/Docs, Itiraz/Takip/Upsell/Referans/Lead Toplama gibi
  admin/destek isleri n8n'de kalir.

Bu modul her n8n workflow icin: id, ad, webhook path, kullanim aciklamasi
tutar. ``n8n_call_workflow`` tool'u bu registry'den match ederek webhook
URL'ini olusturur ve POST atar. Yeni bir workflow eklendiginde sadece
buraya bir satir eklenir; tool kodu degismez.

Base URL env'den (``N8N_BASE_URL``, ornek: ``https://mindidai.app.n8n.cloud``).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class N8nWorkflow:
    name: str           # MindBot'un kullandigi takma ad (snake_case)
    workflow_id: str    # n8n UI'deki id
    webhook_path: str   # /webhook/<path> — slash dahil yazilmaz; otomatik eklenir
    description: str    # ne yapar (TR)
    http_method: str = "POST"


# Bilinen workflow listesi. agent_tools (jRtC1XlmklzQzHSO) icindeki 11
# alt-endpoint ayri kayit olarak; cunku MindBot her birini ayri "tool" gibi
# gormeli.
N8N_REGISTRY: list[N8nWorkflow] = [
    # ----- agent_tools (11 endpoint) -----
    N8nWorkflow(
        name="drive_upload",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="drive/upload",
        description=(
            "Google Drive'a dosya yukler. Body: {filename, content_base64, "
            "folder_id?}. n8n agent_tools alt endpoint."
        ),
    ),
    N8nWorkflow(
        name="drive_download",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="drive/download",
        description=(
            "Drive'dan dosya cek. Body: {file_id}. Return: base64 + meta."
        ),
        http_method="GET",
    ),
    N8nWorkflow(
        name="drive_share",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="drive/share",
        description="Drive dosyasini paylas. Body: {file_id, email, role}.",
    ),
    N8nWorkflow(
        name="drive_list",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="drive/list",
        description="Drive klasoru listele. Body: {folder_id?, query?}.",
        http_method="GET",
    ),
    N8nWorkflow(
        name="sheets_read",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="sheets/read",
        description="Google Sheets oku. Body: {sheet_id, range}.",
        http_method="GET",
    ),
    N8nWorkflow(
        name="sheets_append",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="sheets/append",
        description="Sheets'e satir ekle. Body: {sheet_id, values: [...]}.",
    ),
    N8nWorkflow(
        name="docs_get",
        workflow_id="jRtC1XlmklzQzHSO",
        webhook_path="docs/get",
        description="Google Docs icerigini oku. Body: {doc_id}.",
        http_method="GET",
    ),
    # ----- Sales workflowlari (kalir, mind-agent ile cakismaz) -----
    N8nWorkflow(
        name="itiraz_agent",
        workflow_id="9nTdKNPLCjo8DKfE",
        webhook_path="itiraz-gelen",
        description=(
            "Mindid B2B itiraz handler. Body: {musteri_email, mesaj}. "
            "Gemini ile siniflandirir, Seyma'ya oneri maili gonderir "
            "(insan onayli — otomatik musteriye yollamaz)."
        ),
    ),
    N8nWorkflow(
        name="lead_toplama",
        workflow_id="l31p16NRZeyk4eEm",
        webhook_path="lead-toplama",
        description=(
            "Webhook ile lead alip skor + NocoDB kayit + mail. Body: "
            "{ad_soyad, email, telefon, kaynak, sirket, ...}."
        ),
    ),
    N8nWorkflow(
        name="bekci_alert",
        workflow_id="JQrjJcDRuYKTpMkC",
        webhook_path="bekci-alert",
        description=(
            "Bekci Robot (Guardian) alert tetikleyici. Mind-agent'in "
            "Guardian runner'i RED/YELLOW kararinda buraya POST atar "
            "(body: level, reason, metrics, timestamp, pause_outreach). "
            "n8n Gmail node'u Seyma'ya HTML mail gonderir."
        ),
    ),
    N8nWorkflow(
        name="lead_onboarding",
        workflow_id="nz8tNAR737yjrQRS",
        webhook_path="",  # Schedule-driven, webhook yok
        description=(
            "Lead Onboarding sequence: asama=Sicak leadlere 3 asamali "
            "welcome dizisi (anında / 24sa / 72sa). Saatte 1 calisir, "
            "state machine NocoDB onboarding_step kolonunda. Slowdays "
            "leadleri exclude. HARD_CAP 50/run. Schedule-driven — bu "
            "tool MindBot'tan TETIKLENEMEZ, sadece bilgi amacli registry'de."
        ),
    ),
]


def find_workflow(name: str) -> N8nWorkflow | None:
    """Case-insensitive name lookup."""
    n = (name or "").strip().lower()
    for wf in N8N_REGISTRY:
        if wf.name == n:
            return wf
    return None


__all__ = ["N8nWorkflow", "N8N_REGISTRY", "find_workflow"]
