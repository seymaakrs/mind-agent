"""Faz C tests — Image/Video/Marketing agentlarinin brand_identity erisimi.

Bu testler:
- BRAND_AWARE_PREFIX'in 3 agent talimatina prepend edildigini,
- fetch_brand_identity tool'unun 3 agent tool listesinde oldugunu
dogrular. LLM cagrilmaz (offline wiring testleri).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


class TestFazCImageAgent:
    def test_image_agent_has_fetch_brand_identity(self):
        from src.agents.image_agent import create_image_agent

        agent = create_image_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"image agent missing fetch_brand_identity. Got: {tool_names}"
        )

    def test_image_agent_instructions_have_brand_prefix(self):
        from src.agents.image_agent import create_image_agent

        agent = create_image_agent()
        assert "fetch_brand_identity" in agent.instructions
        assert "BRAND CONTEXT" in agent.instructions
        assert "Faz C" in agent.instructions


class TestFazCVideoAgent:
    def test_video_agent_has_fetch_brand_identity(self):
        from src.agents.video_agent import create_video_agent

        agent = create_video_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"video agent missing fetch_brand_identity. Got: {tool_names}"
        )

    def test_video_agent_instructions_have_brand_prefix(self):
        from src.agents.video_agent import create_video_agent

        agent = create_video_agent()
        assert "fetch_brand_identity" in agent.instructions
        assert "BRAND CONTEXT" in agent.instructions


class TestFazCMarketingAgent:
    def test_marketing_agent_has_fetch_brand_identity(self):
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        tool_names = {t.name for t in agent.tools}
        assert "fetch_brand_identity" in tool_names, (
            f"marketing agent missing fetch_brand_identity. Got: {tool_names}"
        )

    def test_marketing_agent_instructions_have_brand_prefix(self):
        from src.agents.marketing_agent import create_marketing_agent

        agent = create_marketing_agent()
        assert "fetch_brand_identity" in agent.instructions
        assert "BRAND CONTEXT" in agent.instructions
        # Mevcut talimat icerigi de korunmus olmali
        assert "ABSOLUTE RULE #1" in agent.instructions
        assert "WORKFLOWS" in agent.instructions


class TestFazCPrefixContent:
    def test_prefix_includes_fallback_guidance(self):
        """Prefix exists=False / hata durumlarini ele almali."""
        from src.agents.instructions import BRAND_AWARE_PREFIX

        text = BRAND_AWARE_PREFIX.lower()
        assert "exists=false" in text or "exists=true" in text
        assert "fetch_business" in text  # fallback
        assert "avoid_words" in text  # voice rule
        assert "image_donts" in text  # visual rule
