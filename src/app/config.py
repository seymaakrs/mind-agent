from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# Load .env so the settings model can read environment variables easily.
load_dotenv()


class Settings(BaseModel):
    """Uygulama genelinde kullanilan temel ayarlar."""

    model_config = ConfigDict(populate_by_name=True)

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")

    # Google AI (Gemini API for image/video generation)
    google_ai_api_key: str | None = Field(default=None, alias="GOOGLE_AI_API_KEY")

    # Vertex AI / GCP
    gcp_project_id: str | None = Field(default=None, alias="GCP_PROJECT_ID")
    gcp_location: str | None = Field(default="us-central1", alias="GCP_LOCATION")

    # Firebase
    firebase_credentials_file: str | None = Field(
        default=None, alias="FIREBASE_CREDENTIALS_FILE"
    )
    firebase_storage_bucket: str | None = Field(
        default=None, alias="FIREBASE_STORAGE_BUCKET"
    )

    # Late API (Instagram posting via Late)
    late_api_key: str | None = Field(default=None, alias="LATE_API_KEY")

    # fal.ai (MMAudio - video audio generation)
    fal_key: str | None = Field(default=None, alias="FAL_KEY")

    # Serper.dev (Google SERP API for SEO analysis)
    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")

    # Kling AI (Video generation)
    kling_access_key: str | None = Field(default=None, alias="KLING_ACCESS_KEY")
    kling_secret_key: str | None = Field(default=None, alias="KLING_SECRET_KEY")

    # HeyGen AI (Video Agent)
    heygen_api_key: str | None = Field(default=None, alias="HEYGEN_API_KEY")

    # Mind-agent /task endpoint authentication (Bearer token)
    mind_agent_api_key: str | None = Field(default=None, alias="MIND_AGENT_API_KEY")

    # NocoDB CRM (customer_agent ekosistemi — Leadler/Pipeline/Etkilesimler)
    # Sozlesme: docs/customer-integration-contract.md, Bolum 2.
    nocodb_base_url: str | None = Field(default=None, alias="NOCODB_BASE_URL")
    nocodb_api_token: str | None = Field(default=None, alias="NOCODB_API_TOKEN")
    nocodb_base_id: str | None = Field(default=None, alias="NOCODB_BASE_ID")
    nocodb_table_leads: str | None = Field(default=None, alias="NOCODB_TABLE_LEADS")
    nocodb_table_pipeline: str | None = Field(default=None, alias="NOCODB_TABLE_PIPELINE")
    nocodb_table_etkilesimler: str | None = Field(
        default=None, alias="NOCODB_TABLE_ETKILESIMLER"
    )

    # n8n webhook base URL (customer_agent tetikleyicileri)
    n8n_base_url: str | None = Field(default=None, alias="N8N_BASE_URL")

    # Dry-run mode - Google API'lerine gercek cagri yapmadan prompt'lari loglar
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    @classmethod
    def from_env(cls) -> "Settings":
        """Ortami okuyup Settings ornegi dondurur."""
        return cls.model_validate(
            {
                "openai_api_key": os.getenv("OPENAI_API_KEY"),
                "openai_model": os.getenv("OPENAI_MODEL"),
                "google_ai_api_key": os.getenv("GOOGLE_AI_API_KEY"),
                "gcp_project_id": os.getenv("GCP_PROJECT_ID"),
                "gcp_location": os.getenv("GCP_LOCATION"),
                "firebase_credentials_file": os.getenv("FIREBASE_CREDENTIALS_FILE"),
                "firebase_storage_bucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
                "late_api_key": os.getenv("LATE_API_KEY"),
                "fal_key": os.getenv("FAL_KEY"),
                "serper_api_key": os.getenv("SERPER_API_KEY"),
                "dry_run": os.getenv("DRY_RUN", "").lower() in ("true", "1", "yes"),
                "kling_access_key": os.getenv("KLING_ACCESS_KEY"),
                "kling_secret_key": os.getenv("KLING_SECRET_KEY"),
                "heygen_api_key": os.getenv("HEYGEN_API_KEY"),
                "mind_agent_api_key": os.getenv("MIND_AGENT_API_KEY"),
                "nocodb_base_url": os.getenv("NOCODB_BASE_URL"),
                "nocodb_api_token": os.getenv("NOCODB_API_TOKEN"),
                "nocodb_base_id": os.getenv("NOCODB_BASE_ID"),
                "nocodb_table_leads": os.getenv("NOCODB_TABLE_LEADS"),
                "nocodb_table_pipeline": os.getenv("NOCODB_TABLE_PIPELINE"),
                "nocodb_table_etkilesimler": os.getenv("NOCODB_TABLE_ETKILESIMLER"),
                "n8n_base_url": os.getenv("N8N_BASE_URL"),
            }
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings ornegini cache'leyerek disari sunar."""
    return Settings.from_env()


class ModelSettings(BaseModel):
    """Firebase'den okunan model ayarlari."""

    orchestrator_model: str = "gpt-4o"
    image_agent_model: str = "gpt-4o"
    video_agent_model: str = "gpt-4o"
    marketing_agent_model: str = "gpt-4o"
    web_agent_model: str = "gpt-4o"
    analysis_agent_model: str = "gpt-4o"
    image_generation_model: str = "gemini-2.5-flash-image"
    video_generation_model: str = "veo-3.1-generate-preview"
    vertex_video_model: str = "veo-2.0-generate-001"
    kling_video_model: str = "kling-v3"


# Cache for model settings
_model_settings_cache: ModelSettings | None = None


def _load_model_settings_from_firebase() -> dict[str, Any]:
    """Firebase'den settings/app_settings dokumanini okur."""
    from src.infra.firebase_client import get_document_client

    doc_client = get_document_client("settings")
    doc = doc_client.get_document("app_settings")
    return doc or {}


def get_model_settings() -> ModelSettings:
    """
    Firebase'den model ayarlarini okur ve cache'ler.

    Firestore path: settings/app_settings
    Fields (camelCase):
        - orchestratorModel
        - imageAgentModel
        - videoAgentModel
        - marketingModel
        - imageGenerationModel
        - videoGenerationModel
        - vertexVideoModel
    """
    global _model_settings_cache

    if _model_settings_cache is not None:
        return _model_settings_cache

    try:
        doc = _load_model_settings_from_firebase()

        _model_settings_cache = ModelSettings(
            orchestrator_model=doc.get("orchestratorModel", "gpt-4o"),
            image_agent_model=doc.get("imageAgentModel", "gpt-4o"),
            video_agent_model=doc.get("videoAgentModel", "gpt-4o"),
            marketing_agent_model=doc.get("marketingModel", "gpt-4o"),  # Firebase uses "marketingModel"
            web_agent_model=doc.get("webAgentModel", "gpt-4o"),
            analysis_agent_model=doc.get("analysisAgent", "gpt-4o"),
            image_generation_model=doc.get("imageGenerationModel", "gemini-2.5-flash-image"),
            video_generation_model=doc.get("videoGenerationModel", "veo-3.1-generate-preview"),
            vertex_video_model=doc.get("vertexVideoModel", "veo-2.0-generate-001"),
            kling_video_model=doc.get("klingVideoModel", "kling-v3"),
        )
    except Exception:
        # Firebase hatasi olursa default degerleri kullan
        _model_settings_cache = ModelSettings()

    return _model_settings_cache


def clear_model_settings_cache() -> None:
    """Model settings cache'ini temizler (test veya reload icin)."""
    global _model_settings_cache
    _model_settings_cache = None


# ---------------------------------------------------------------------------
# Dynamic Agent Instructions (Firebase: settings/agent_instructions)
# ---------------------------------------------------------------------------


class PromptFieldConfig(BaseModel):
    """Tek bir Pydantic field'inin override bilgisi (description + examples)."""

    description: str
    examples: list[Any] = []


class AgentInstructionConfig(BaseModel):
    """Agent persona + prompt field override konfigurasyonu."""

    persona: str | None = None
    prompt_fields: dict[str, PromptFieldConfig] = {}


# Cache for agent instructions
_agent_instructions_cache: dict[str, AgentInstructionConfig] | None = None


def _load_agent_instructions_from_firebase() -> dict[str, Any]:
    """Firebase'den settings/agent_instructions dokumanini okur."""
    from src.infra.firebase_client import get_document_client

    doc_client = get_document_client("settings")
    doc = doc_client.get_document("agent_instructions")
    return doc or {}


def _parse_agent_instructions(raw: dict[str, Any]) -> dict[str, AgentInstructionConfig]:
    """Firebase raw dict'ini AgentInstructionConfig dict'ine donusturur."""
    result: dict[str, AgentInstructionConfig] = {}
    for agent_name, agent_data in raw.items():
        if not isinstance(agent_data, dict):
            continue
        prompt_fields: dict[str, PromptFieldConfig] = {}
        raw_fields = agent_data.get("prompt_fields", {})
        if isinstance(raw_fields, dict):
            for field_name, field_data in raw_fields.items():
                if isinstance(field_data, dict) and "description" in field_data:
                    prompt_fields[field_name] = PromptFieldConfig(**field_data)
        result[agent_name] = AgentInstructionConfig(
            persona=agent_data.get("persona"),
            prompt_fields=prompt_fields,
        )
    return result


def get_agent_instructions(agent_name: str) -> AgentInstructionConfig:
    """
    Firebase settings/agent_instructions'dan agent config okur ve cache'ler.

    Fallback: Firebase hatasi veya agent bulunamazsa bos AgentInstructionConfig doner.
    """
    global _agent_instructions_cache

    if _agent_instructions_cache is None:
        try:
            raw = _load_agent_instructions_from_firebase()
            _agent_instructions_cache = _parse_agent_instructions(raw)
        except Exception:
            # Firebase hatasi — bos cache ile devam et, sistem kirilmaz
            _agent_instructions_cache = {}

    return _agent_instructions_cache.get(agent_name, AgentInstructionConfig())


def clear_agent_instructions_cache() -> None:
    """Agent instructions cache'ini temizler (test veya reload icin)."""
    global _agent_instructions_cache
    _agent_instructions_cache = None


# ---------------------------------------------------------------------------
# Customer Agent Feature Flags (Firebase: settings/app_settings.customerAgent)
# ---------------------------------------------------------------------------
#
# Mind-agent'in customer_agent ekosistemine (NocoDB + n8n) entegrasyonunu
# kontrol eden sub-flag'ler. Tasarim ilkeleri:
#
# 1. Master + sub-flag: enabled=False iken hicbir customer kapasitesi
#    calismaz. Sub-flag'ler bagimsiz acilir, asamali rollout.
# 2. Default kapali: tum bayraklar False ile baslar — yanlislikla acik kalmis
#    bir kapasitenin riski sifir.
# 3. Tolerant reader: Firestore'da kolon yoksa veya tip yanlissa False.
# 4. Fail-closed: Firestore hata verirse hepsi False — sistem kirilmaz.
#
# Sozlesme: docs/customer-integration-contract.md, Bolum 5.


class CustomerAgentFlags(BaseModel):
    """customer_agent kapasitelerinin asamali acilis bayraklari."""

    enabled: bool = False
    can_read_leads: bool = False
    can_read_pipeline: bool = False
    can_attach_reports: bool = False
    can_trigger_followup: bool = False
    can_post_for_lead: bool = False

    def is_capability_enabled(self, capability: str) -> bool:
        """
        Bir kapasitenin gercekten acik olup olmadigini doner.

        Master switch (enabled) kapaliysa hicbir kapasite acik sayilmaz.
        Bilinmeyen kapasite adi → False (sessiz fail-closed).
        """
        if not self.enabled:
            return False
        return bool(getattr(self, capability, False))


_customer_agent_flags_cache: CustomerAgentFlags | None = None


def _load_app_settings_from_firebase() -> dict[str, Any]:
    """Firebase'den settings/app_settings dokumanini okur (TUM doc)."""
    from src.infra.firebase_client import get_document_client

    doc_client = get_document_client("settings")
    doc = doc_client.get_document("app_settings")
    return doc or {}


def _parse_customer_agent_flags(raw: dict[str, Any]) -> CustomerAgentFlags:
    """Firestore raw dict'inden CustomerAgentFlags olusturur (camelCase → snake_case)."""
    section = raw.get("customerAgent", {})
    if not isinstance(section, dict):
        return CustomerAgentFlags()
    return CustomerAgentFlags(
        enabled=bool(section.get("enabled", False)),
        can_read_leads=bool(section.get("canReadLeads", False)),
        can_read_pipeline=bool(section.get("canReadPipeline", False)),
        can_attach_reports=bool(section.get("canAttachReports", False)),
        can_trigger_followup=bool(section.get("canTriggerFollowup", False)),
        can_post_for_lead=bool(section.get("canPostForLead", False)),
    )


def get_customer_agent_flags() -> CustomerAgentFlags:
    """
    Customer agent feature flag'lerini Firestore'dan okur ve cache'ler.

    Firestore path: settings/app_settings.customerAgent
    Hata durumunda tum bayraklar False (fail-closed).
    """
    global _customer_agent_flags_cache

    if _customer_agent_flags_cache is not None:
        return _customer_agent_flags_cache

    try:
        raw = _load_app_settings_from_firebase()
        _customer_agent_flags_cache = _parse_customer_agent_flags(raw)
    except Exception:
        # Firestore hatasi → hepsi kapali, sistem kirilmaz
        _customer_agent_flags_cache = CustomerAgentFlags()

    return _customer_agent_flags_cache


def clear_customer_agent_flags_cache() -> None:
    """Customer agent flags cache'ini temizler (test veya runtime reload icin)."""
    global _customer_agent_flags_cache
    _customer_agent_flags_cache = None


__all__ = [
    "Settings",
    "get_settings",
    "ModelSettings",
    "get_model_settings",
    "clear_model_settings_cache",
    "PromptFieldConfig",
    "AgentInstructionConfig",
    "get_agent_instructions",
    "clear_agent_instructions_cache",
    "CustomerAgentFlags",
    "get_customer_agent_flags",
    "clear_customer_agent_flags_cache",
]
