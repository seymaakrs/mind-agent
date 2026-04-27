"""
Orchestrator -> customer_agent wiring testi.

Kritik regresyon guvencesi:
- customerAgent.enabled=False (default) iken orchestrator'in tool listesinde
  customer_agent_tool BULUNMAMALI. Mevcut akislari (image/video/marketing/
  analysis/orchestrator) etkilemediginden emin oluyoruz.
- enabled=True iken customer_agent_tool listede BULUNMALI.

Strateji: Orchestrator'i gercekten ayaga kaldirmadan (Firestore/OpenAI
init'leri yavas) sadece "tool seciminin" kosulunu test ediyoruz —
src.agents.orchestrator_agent modulunun "if customer_flags.enabled"
dalini, downstream agent factory'leri mock'layarak.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import MagicMock, patch

import pytest

from src.app.config import (
    CustomerAgentFlags,
    clear_customer_agent_flags_cache,
)


@pytest.fixture(autouse=True)
def reset_flags():
    clear_customer_agent_flags_cache()
    yield
    clear_customer_agent_flags_cache()


def _build_orchestrator_with_flags(flags: CustomerAgentFlags):
    """
    create_orchestrator_agent'i, downstream factory'leri mock'layarak calistirir
    ve donen Agent'in tool isim setini doner.

    Mock'lanan'lar:
      - get_customer_agent_flags → patched flags
      - create_marketing_agent / create_analysis_agent / create_customer_agent
        → fake Agent instance (cunku gercek factory'ler Firestore'a gidiyor)
      - get_model_settings → fake (gpt-4o)
      - Agent constructor'a giden tools listesini yakalayalim
    """
    from src.app.config import ModelSettings

    fake_agent = MagicMock(name="FakeSubAgent")

    captured: dict = {}

    class FakeAgent:
        def __init__(self, *, tools, **kwargs):
            captured["tools"] = tools
            self.tools = tools
            self.name = kwargs.get("name", "orchestrator")

    with patch(
        "src.agents.orchestrator_agent.get_customer_agent_flags",
        return_value=flags,
    ), patch(
        "src.agents.orchestrator_agent.get_model_settings",
        return_value=ModelSettings(),
    ), patch(
        "src.agents.orchestrator_agent.create_marketing_agent",
        return_value=fake_agent,
    ), patch(
        "src.agents.orchestrator_agent.create_analysis_agent",
        return_value=fake_agent,
    ), patch(
        "src.agents.orchestrator_agent.create_customer_agent",
        return_value=fake_agent,
    ), patch(
        "src.agents.orchestrator_agent.Agent",
        new=FakeAgent,
    ):
        from src.agents.orchestrator_agent import create_orchestrator_agent

        create_orchestrator_agent()

    # tool listesindeki her oge bir FunctionTool — name attribute ile.
    return {getattr(t, "name", "<no_name>") for t in captured["tools"]}


def test_customer_tool_absent_when_flag_off():
    """customerAgent.enabled=False → customer_agent_tool tool listesinde YOK."""
    names = _build_orchestrator_with_flags(CustomerAgentFlags(enabled=False))
    assert "customer_agent_tool" not in names, (
        f"Beklenmedik: customer_agent_tool flag kapaliyken eklenmis. Tools: {names}"
    )


def test_customer_tool_present_when_flag_on():
    """customerAgent.enabled=True → customer_agent_tool tool listesinde VAR."""
    names = _build_orchestrator_with_flags(CustomerAgentFlags(enabled=True))
    assert "customer_agent_tool" in names, (
        f"Beklenen tool eksik. Tools: {names}"
    )


def test_existing_tools_unchanged_with_flag_off():
    """Flag kapali iken eski tool'larin hepsi yine listede (regresyon kontrolu)."""
    names = _build_orchestrator_with_flags(CustomerAgentFlags(enabled=False))
    expected = {
        "image_agent_tool",
        "video_agent_tool",
        "marketing_agent_tool",
        "analysis_agent_tool",
        "fetch_business",
    }
    missing = expected - names
    assert not missing, f"Eski tool'lar regresyona ugradi! Eksik: {missing}"


def test_existing_tools_unchanged_with_flag_on():
    """Flag acik olsa da eski tool'lar olduğu gibi (kapsama esitligi)."""
    names = _build_orchestrator_with_flags(CustomerAgentFlags(enabled=True))
    expected = {
        "image_agent_tool",
        "video_agent_tool",
        "marketing_agent_tool",
        "analysis_agent_tool",
        "fetch_business",
    }
    assert expected.issubset(names)
