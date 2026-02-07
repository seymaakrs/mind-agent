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
                "dry_run": os.getenv("DRY_RUN", "").lower() in ("true", "1", "yes"),
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
        )
    except Exception:
        # Firebase hatasi olursa default degerleri kullan
        _model_settings_cache = ModelSettings()

    return _model_settings_cache


def clear_model_settings_cache() -> None:
    """Model settings cache'ini temizler (test veya reload icin)."""
    global _model_settings_cache
    _model_settings_cache = None


__all__ = ["Settings", "get_settings", "ModelSettings", "get_model_settings", "clear_model_settings_cache"]
