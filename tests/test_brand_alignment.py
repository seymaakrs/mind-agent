"""Tests for Faz C: content agentlari (marketing/image/video) brand identity
okuyabilsin ve prompt'larina marka kimligini enjekte etsin.

Bu testler:
- Her agent'in fetch_brand_identity tool'una sahip oldugunu,
- Instruction prompt'larinin brand alignment workflow'unu icerdigini
dogrular. LLM cagrilmaz (offline wiring).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


class TestBrandToolWiring:
    def test_marketing_agent_has_fetch_brand_identity(self):
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"marketing agent missing fetch_brand_identity. tools: {tool_names}"
        )

    def test_image_agent_has_fetch_brand_identity(self):
        from src.agents.image_agent import create_image_agent

        agent = create_image_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"image agent missing fetch_brand_identity. tools: {tool_names}"
        )

    def test_video_agent_has_fetch_brand_identity(self):
        from src.agents.video_agent import create_video_agent

        agent = create_video_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"video agent missing fetch_brand_identity. tools: {tool_names}"
        )


class TestBrandAlignmentInstructions:
    def test_marketing_instructions_mention_brand_workflow(self):
        from src.agents.instructions import MARKETING_AGENT_INSTRUCTIONS

        text = MARKETING_AGENT_INSTRUCTIONS.lower()
        assert "fetch_brand_identity" in text, (
            "marketing prompt must reference fetch_brand_identity"
        )
        # The prompt should mention at least one of the brand voice concepts
        assert any(k in text for k in ["avoid_words", "preferred_words", "voice"]), (
            "marketing prompt must mention brand voice concepts"
        )

    def test_image_instructions_mention_brand_workflow(self):
        from src.agents.instructions import IMAGE_AGENT_CORE_INSTRUCTIONS

        text = IMAGE_AGENT_CORE_INSTRUCTIONS.lower()
        assert "fetch_brand_identity" in text
        # Visual brand concepts the image agent must respect
        assert any(
            k in text for k in ["primary_colors", "visual_style", "image_donts"]
        ), "image prompt must mention brand visual concepts"

    def test_video_instructions_mention_brand_workflow(self):
        from src.agents.instructions import VIDEO_AGENT_CORE_INSTRUCTIONS

        text = VIDEO_AGENT_CORE_INSTRUCTIONS.lower()
        assert "fetch_brand_identity" in text
        assert any(
            k in text for k in ["primary_colors", "visual_style", "image_donts"]
        ), "video prompt must mention brand visual concepts"
