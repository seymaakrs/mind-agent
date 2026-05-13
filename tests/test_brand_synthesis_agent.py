"""Tests for Brand Synthesis Agent wiring (Faz B1).

Brand Synthesis Agent ham isletme verisini (businesses/{id} + eski profile
map) okuyup kanonik BrandIdentity onerisini Firestore'a 'ai_synthesis' /
'draft' kaynagiyla yazar. Kullanici onayindan sonra source 'manual'a doner.

Bu testler agent'in:
- dogru tool setine sahip oldugunu,
- registry'de gorundugunu,
- instruction prompt'unun gerekli anahtar kavramlari icerdigini
dogrular. LLM cagrilmaz (offline wiring testleri).
"""
from __future__ import annotations

import os

import pytest

# Agents modulu OPENAI_API_KEY arar; offline import icin fake key.
os.environ.setdefault("OPENAI_API_KEY", "test")


class TestBrandSynthesisAgentWiring:
    def test_agent_name_and_handoff(self):
        from src.agents.brand_synthesis_agent import create_brand_synthesis_agent

        agent = create_brand_synthesis_agent()
        assert agent.name == "brand_synthesis"
        assert agent.handoff_description
        assert "marka" in agent.handoff_description.lower()

    def test_agent_has_required_tools(self):
        """Brand Synthesis must read business + read/write brand_identity."""
        from src.agents.brand_synthesis_agent import create_brand_synthesis_agent

        agent = create_brand_synthesis_agent()
        tool_names = {t.name for t in agent.tools}
        required = {
            "fetch_business",
            "fetch_brand_identity",
            "update_brand_identity",
        }
        missing = required - tool_names
        assert not missing, f"Missing tools: {missing}. Got: {tool_names}"

    def test_agent_does_not_have_unrelated_tools(self):
        """Synthesis agent should be focused — no image/video/post tools."""
        from src.agents.brand_synthesis_agent import create_brand_synthesis_agent

        agent = create_brand_synthesis_agent()
        tool_names = {t.name for t in agent.tools}
        forbidden = {
            "generate_image",
            "generate_video",
            "post_on_instagram",
            "upsert_lead",
        }
        leaked = forbidden & tool_names
        assert not leaked, f"Synthesis agent leaked tools: {leaked}"

    def test_registry_exposes_brand_synthesis(self):
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        assert "brand_synthesis" in registry
        agent = registry["brand_synthesis"]()
        assert agent.name == "brand_synthesis"


class TestBrandSynthesisInstructions:
    def test_instructions_constant_exported(self):
        from src.agents.instructions import BRAND_SYNTHESIS_AGENT_INSTRUCTIONS

        assert isinstance(BRAND_SYNTHESIS_AGENT_INSTRUCTIONS, str)
        assert len(BRAND_SYNTHESIS_AGENT_INSTRUCTIONS) > 500, (
            "Instructions look too short to be a real agent prompt"
        )

    def test_instructions_describe_workflow(self):
        """Prompt must walk through fetch → propose → validate → save."""
        from src.agents.instructions import BRAND_SYNTHESIS_AGENT_INSTRUCTIONS

        text = BRAND_SYNTHESIS_AGENT_INSTRUCTIONS.lower()
        # Required tool names
        assert "fetch_business" in text
        assert "fetch_brand_identity" in text
        assert "update_brand_identity" in text
        # Key concepts
        assert "business_id" in text
        # Source flag — synthesis output must NOT overwrite human edits
        assert "ai_synthesis" in text or "draft" in text

    def test_instructions_warn_against_overwriting_manual(self):
        """Synthesis must not overwrite 'manual' (human-edited) fields blindly."""
        from src.agents.instructions import BRAND_SYNTHESIS_AGENT_INSTRUCTIONS

        text = BRAND_SYNTHESIS_AGENT_INSTRUCTIONS.lower()
        # Either explicit guard wording or 'manual' source check
        assert "manual" in text, (
            "Prompt must mention the 'manual' source to avoid overwriting "
            "human-edited brand identity."
        )

    def test_instructions_require_schema_fields(self):
        """Prompt should reference the 6 sub-models so the LLM fills each."""
        from src.agents.instructions import BRAND_SYNTHESIS_AGENT_INSTRUCTIONS

        text = BRAND_SYNTHESIS_AGENT_INSTRUCTIONS.lower()
        for section in [
            "basics",
            "visual",
            "voice",
            "audience",
            "content_strategy",
            "business_context",
        ]:
            assert section in text, f"Missing section in prompt: {section}"
