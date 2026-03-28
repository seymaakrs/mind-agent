"""Tests for dynamic agent instructions — config loading, prompt model building, and agent creation."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from pydantic import BaseModel

from src.app.config import (
    AgentInstructionConfig,
    PromptFieldConfig,
    get_agent_instructions,
    clear_agent_instructions_cache,
)
from src.models.prompts import (
    ImagePrompt,
    VideoPrompt,
    build_image_prompt_model,
    build_video_prompt_model,
)


# ---------------------------------------------------------------------------
# AgentInstructionConfig model tests
# ---------------------------------------------------------------------------


class TestAgentInstructionConfig:
    """PromptFieldConfig ve AgentInstructionConfig Pydantic model testleri."""

    def test_prompt_field_config_defaults(self):
        """PromptFieldConfig: description required, examples default bos liste."""
        cfg = PromptFieldConfig(description="test desc")
        assert cfg.description == "test desc"
        assert cfg.examples == []

    def test_prompt_field_config_with_examples(self):
        """PromptFieldConfig: examples verilirse saklanir."""
        cfg = PromptFieldConfig(description="d", examples=["ex1", "ex2"])
        assert cfg.examples == ["ex1", "ex2"]

    def test_agent_instruction_config_defaults(self):
        """AgentInstructionConfig: persona None, prompt_fields bos dict."""
        cfg = AgentInstructionConfig()
        assert cfg.persona is None
        assert cfg.prompt_fields == {}

    def test_agent_instruction_config_full(self):
        """AgentInstructionConfig: tum alanlar dolu."""
        cfg = AgentInstructionConfig(
            persona="Custom persona",
            prompt_fields={
                "scene": PromptFieldConfig(
                    description="Custom scene desc",
                    examples=["Custom example"],
                ),
            },
        )
        assert cfg.persona == "Custom persona"
        assert "scene" in cfg.prompt_fields
        assert cfg.prompt_fields["scene"].description == "Custom scene desc"


# ---------------------------------------------------------------------------
# get_agent_instructions tests (Firebase mocked)
# ---------------------------------------------------------------------------


class TestGetAgentInstructions:
    """Firebase'den agent instruction okuma + cache + fallback testleri."""

    def setup_method(self):
        clear_agent_instructions_cache()

    def teardown_method(self):
        clear_agent_instructions_cache()

    @patch("src.app.config._load_agent_instructions_from_firebase")
    def test_returns_config_from_firebase(self, mock_load):
        """Firebase'de config varsa dogru AgentInstructionConfig doner."""
        mock_load.return_value = {
            "image_agent": {
                "persona": "Firebase persona",
                "prompt_fields": {
                    "scene": {
                        "description": "Firebase scene desc",
                        "examples": ["fb example"],
                    }
                },
            }
        }

        config = get_agent_instructions("image_agent")
        assert config.persona == "Firebase persona"
        assert config.prompt_fields["scene"].description == "Firebase scene desc"
        mock_load.assert_called_once()

    @patch("src.app.config._load_agent_instructions_from_firebase")
    def test_returns_empty_config_for_unknown_agent(self, mock_load):
        """Firebase'de olmayan agent icin bos AgentInstructionConfig doner."""
        mock_load.return_value = {}

        config = get_agent_instructions("nonexistent_agent")
        assert config.persona is None
        assert config.prompt_fields == {}

    @patch("src.app.config._load_agent_instructions_from_firebase")
    def test_caches_after_first_load(self, mock_load):
        """Ikinci cagri Firebase'e gitmez, cache'den okur."""
        mock_load.return_value = {"image_agent": {"persona": "cached"}}

        get_agent_instructions("image_agent")
        get_agent_instructions("image_agent")

        mock_load.assert_called_once()

    @patch("src.app.config._load_agent_instructions_from_firebase")
    def test_clear_cache_forces_reload(self, mock_load):
        """clear_agent_instructions_cache sonrasi tekrar Firebase'e gider."""
        mock_load.return_value = {}

        get_agent_instructions("image_agent")
        clear_agent_instructions_cache()
        get_agent_instructions("image_agent")

        assert mock_load.call_count == 2

    @patch("src.app.config._load_agent_instructions_from_firebase")
    def test_firebase_error_returns_empty_config(self, mock_load):
        """Firebase hatasi durumunda fallback — bos config doner, sistem kırılmaz."""
        mock_load.side_effect = Exception("Firebase connection error")

        config = get_agent_instructions("image_agent")
        assert config.persona is None
        assert config.prompt_fields == {}


# ---------------------------------------------------------------------------
# build_image_prompt_model tests
# ---------------------------------------------------------------------------


class TestBuildImagePromptModel:
    """Dynamic ImagePrompt model building testleri."""

    def test_no_overrides_returns_original(self):
        """Override yoksa orijinal ImagePrompt donmeli."""
        config = AgentInstructionConfig()
        model = build_image_prompt_model(config)
        assert model is ImagePrompt

    def test_override_scene_description(self):
        """scene field description override edilmeli."""
        config = AgentInstructionConfig(
            prompt_fields={
                "scene": PromptFieldConfig(
                    description="Custom scene description for brand X",
                    examples=["A minimalist studio with brand elements"],
                ),
            }
        )
        model = build_image_prompt_model(config)

        # Yeni model olusturulmus olmali
        assert model is not ImagePrompt
        # Override edilmis description kontrolu
        assert "Custom scene description" in model.model_fields["scene"].description

    def test_override_preserves_non_overridden_fields(self):
        """Override edilmeyen field'lar orijinal kalir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "scene": PromptFieldConfig(description="Custom"),
            }
        )
        model = build_image_prompt_model(config)

        # subject orijinal kalmalı
        original_subject_desc = ImagePrompt.model_fields["subject"].description
        assert model.model_fields["subject"].description == original_subject_desc

    def test_to_prompt_string_works_on_dynamic_model(self):
        """Dynamic model'de to_prompt_string() hala calisir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "scene": PromptFieldConfig(description="Override desc"),
            }
        )
        model = build_image_prompt_model(config)

        instance = model(
            scene="Test scene",
            subject="Test subject",
            style="Minimalist",
            colors=["#000", "#fff"],
            mood="Calm",
            composition="Centered",
            lighting="Natural",
            background="White",
        )
        prompt_str = instance.to_prompt_string()
        assert "Test scene" in prompt_str
        assert "Test subject" in prompt_str

    def test_unknown_field_ignored(self):
        """Firebase'de olmayan field adi sessizce ignore edilir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "nonexistent_field": PromptFieldConfig(description="X"),
            }
        )
        model = build_image_prompt_model(config)
        # Bilinmeyen field ignore edilir, orijinal model doner
        assert model is ImagePrompt

    def test_multiple_field_overrides(self):
        """Birden fazla field ayni anda override edilebilir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "scene": PromptFieldConfig(description="Scene override"),
                "mood": PromptFieldConfig(description="Mood override"),
                "lighting": PromptFieldConfig(description="Lighting override"),
            }
        )
        model = build_image_prompt_model(config)
        assert model is not ImagePrompt
        assert "Scene override" in model.model_fields["scene"].description
        assert "Mood override" in model.model_fields["mood"].description
        assert "Lighting override" in model.model_fields["lighting"].description


# ---------------------------------------------------------------------------
# build_video_prompt_model tests
# ---------------------------------------------------------------------------


class TestBuildVideoPromptModel:
    """Dynamic VideoPrompt model building testleri."""

    def test_no_overrides_returns_original(self):
        """Override yoksa orijinal VideoPrompt donmeli."""
        config = AgentInstructionConfig()
        model = build_video_prompt_model(config)
        assert model is VideoPrompt

    def test_override_concept_description(self):
        """concept field description override edilmeli."""
        config = AgentInstructionConfig(
            prompt_fields={
                "concept": PromptFieldConfig(
                    description="Custom concept description",
                    examples=["Cinematic brand reveal"],
                ),
            }
        )
        model = build_video_prompt_model(config)
        assert model is not VideoPrompt
        assert "Custom concept description" in model.model_fields["concept"].description

    def test_to_prompt_string_works_on_dynamic_model(self):
        """Dynamic model'de to_prompt_string() hala calisir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "concept": PromptFieldConfig(description="Override"),
            }
        )
        model = build_video_prompt_model(config)

        instance = model(
            concept="Test concept",
            opening_scene="Opening",
            main_action="Action",
            closing_scene="Closing",
            visual_style="Cinematic",
            color_palette=["#000"],
            mood_atmosphere="Calm",
            camera_movement="Static",
            lighting_style="Natural",
            pacing="Slow",
        )
        prompt_str = instance.to_prompt_string()
        assert "Test concept" in prompt_str

    def test_unknown_field_ignored(self):
        """Bilinmeyen field sessizce ignore edilir."""
        config = AgentInstructionConfig(
            prompt_fields={
                "fake_field": PromptFieldConfig(description="X"),
            }
        )
        model = build_video_prompt_model(config)
        assert model is VideoPrompt


# ---------------------------------------------------------------------------
# Agent creation integration tests
# ---------------------------------------------------------------------------


class TestImageAgentCreation:
    """Image agent'in dynamic config ile olusturulma testi."""

    def setup_method(self):
        clear_agent_instructions_cache()

    def teardown_method(self):
        clear_agent_instructions_cache()

    @patch("src.app.config._load_agent_instructions_from_firebase")
    @patch("src.agents.image_agent.get_model_settings")
    @patch("src.agents.image_agent.get_settings")
    def test_agent_uses_firebase_persona(self, mock_settings, mock_model_settings, mock_load):
        """Firebase persona agent instructions'a inject edilir."""
        mock_settings.return_value = MagicMock(openai_model="gpt-4o")
        mock_model_settings.return_value = MagicMock(image_agent_model="gpt-4o")
        mock_load.return_value = {
            "image_agent": {"persona": "You are a CUSTOM image persona."}
        }

        from src.agents.image_agent import create_image_agent

        agent = create_image_agent()
        assert "You are a CUSTOM image persona." in agent.instructions

    @patch("src.app.config._load_agent_instructions_from_firebase")
    @patch("src.agents.image_agent.get_model_settings")
    @patch("src.agents.image_agent.get_settings")
    def test_agent_uses_default_persona_when_no_firebase(self, mock_settings, mock_model_settings, mock_load):
        """Firebase'de config yoksa default persona kullanilir."""
        mock_settings.return_value = MagicMock(openai_model="gpt-4o")
        mock_model_settings.return_value = MagicMock(image_agent_model="gpt-4o")
        mock_load.return_value = {}

        from src.agents.image_agent import create_image_agent

        agent = create_image_agent()
        assert "expert image generation agent" in agent.instructions


class TestVideoAgentCreation:
    """Video agent'in dynamic config ile olusturulma testi."""

    def setup_method(self):
        clear_agent_instructions_cache()

    def teardown_method(self):
        clear_agent_instructions_cache()

    @patch("src.app.config._load_agent_instructions_from_firebase")
    @patch("src.agents.video_agent.get_model_settings")
    @patch("src.agents.video_agent.get_settings")
    def test_agent_uses_firebase_persona(self, mock_settings, mock_model_settings, mock_load):
        """Firebase persona video agent instructions'a inject edilir."""
        mock_settings.return_value = MagicMock(openai_model="gpt-4o")
        mock_model_settings.return_value = MagicMock(video_agent_model="gpt-4o")
        mock_load.return_value = {
            "video_agent": {"persona": "You are a CUSTOM video persona."}
        }

        from src.agents.video_agent import create_video_agent

        agent = create_video_agent()
        assert "You are a CUSTOM video persona." in agent.instructions
