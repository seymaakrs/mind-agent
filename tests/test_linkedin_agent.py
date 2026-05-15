"""Tests for LinkedIn Mesaj Motoru Agent wiring.

LinkedIn agent lead/kisi bilgisinden kisisellestirilmis baglanti notu +
3 adimli takip dizisi + yanit taslaklari uretir ve NocoDB'ye 'Giden / taslak'
olarak yazar. LinkedIn'de arama/gonderim YAPMAZ.

Bu testler agent'in:
- dogru tool setine sahip oldugunu (NocoDB CRM tools),
- registry'de gorundugunu,
- instruction prompt'unun gerekli kavramlari (gonderim yok, taslak, dizi,
  kanal=LinkedIn) icerdigini
dogrular. LLM cagrilmaz (offline wiring testleri).
"""
from __future__ import annotations

import os

import pytest

# Agents modulu OPENAI_API_KEY arar; offline import icin fake key.
os.environ.setdefault("OPENAI_API_KEY", "test")


class TestLinkedInAgentWiring:
    def test_agent_name_and_handoff(self):
        from src.agents.sales.linkedin_agent import create_linkedin_agent

        agent = create_linkedin_agent()
        assert agent.name == "linkedin"
        assert agent.handoff_description
        assert "linkedin" in agent.handoff_description.lower()

    def test_agent_has_nocodb_tools(self):
        """LinkedIn agent must read leads + log message drafts via NocoDB."""
        from src.agents.sales.linkedin_agent import create_linkedin_agent

        agent = create_linkedin_agent()
        tool_names = {t.name for t in agent.tools}
        required = {
            "query_leads",
            "get_lead",
            "log_lead_message",
            "notify_seyma",
        }
        missing = required - tool_names
        assert not missing, f"Missing tools: {missing}. Got: {tool_names}"

    def test_agent_does_not_have_content_tools(self):
        """Sales agent should be focused — no image/video/post tools."""
        from src.agents.sales.linkedin_agent import create_linkedin_agent

        agent = create_linkedin_agent()
        tool_names = {t.name for t in agent.tools}
        forbidden = {
            "generate_image",
            "generate_video",
            "post_on_instagram",
            "post_on_linkedin",
        }
        leaked = forbidden & tool_names
        assert not leaked, f"LinkedIn agent leaked tools: {leaked}"

    def test_registry_exposes_linkedin(self):
        from src.agents.registry import get_agent_registry

        registry = get_agent_registry()
        assert "linkedin" in registry
        agent = registry["linkedin"]()
        assert agent.name == "linkedin"


class TestLinkedInInstructions:
    def test_instructions_constant_exported(self):
        from src.agents.instructions.sales import LINKEDIN_AGENT_INSTRUCTIONS

        assert isinstance(LINKEDIN_AGENT_INSTRUCTIONS, str)
        assert len(LINKEDIN_AGENT_INSTRUCTIONS) > 500, (
            "Instructions look too short to be a real agent prompt"
        )

    def test_instructions_forbid_sending(self):
        """Core scope guard: this agent must NOT send/search on LinkedIn."""
        from src.agents.instructions.sales import LINKEDIN_AGENT_INSTRUCTIONS

        text = LINKEDIN_AGENT_INSTRUCTIONS.lower()
        # Must explicitly state it does not send / scrape.
        assert "gonderim" in text or "gondermez" in text
        assert "taslak" in text  # output is a draft, not a sent message

    def test_instructions_describe_message_sequence(self):
        """Prompt must include the 3-step follow-up sequence + connection note."""
        from src.agents.instructions.sales import LINKEDIN_AGENT_INSTRUCTIONS

        text = LINKEDIN_AGENT_INSTRUCTIONS.lower()
        assert "baglanti" in text  # connection note
        assert "takip" in text  # follow-up sequence
        assert "log_lead_message" in text  # how drafts are persisted
        assert "linkedin" in text  # kanal

    def test_instructions_no_fabrication_rule(self):
        from src.agents.instructions.sales import LINKEDIN_AGENT_INSTRUCTIONS

        text = LINKEDIN_AGENT_INSTRUCTIONS.lower()
        assert "uydurma" in text, (
            "Prompt must forbid fabricating numbers/claims."
        )
