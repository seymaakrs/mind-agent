"""Sales Director → Reklam Uzmanı peer bridge tool testleri.

Pattern: src.tools.sales.peer_bridge içindeki Runner.run mock'lanır;
gerçek LLM çağrısı yapılmaz.
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.tools.sales import peer_bridge as pb


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_question_rejected():
    out = await pb._ask_reklam_uzmani_impl("", "biz1")
    assert out["success"] is False
    assert "question" in out["error"]


@pytest.mark.asyncio
async def test_whitespace_question_rejected():
    out = await pb._ask_reklam_uzmani_impl("   ", "biz1")
    assert out["success"] is False


@pytest.mark.asyncio
async def test_too_long_question_rejected():
    out = await pb._ask_reklam_uzmani_impl("x" * 2500, "biz1")
    assert out["success"] is False
    assert "too long" in out["error"]


@pytest.mark.asyncio
async def test_empty_business_id_rejected():
    out = await pb._ask_reklam_uzmani_impl("Hangi reklam?", "")
    assert out["success"] is False
    assert "business_id" in out["error"]


# ---------------------------------------------------------------------------
# Happy path — Runner.run mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_answer(monkeypatch):
    """Runner.run mock'lanır, final_output Sales'a döner."""
    fake_result = SimpleNamespace(final_output="Slowdays kampanyası 12 sıcak lead getirdi.")

    async def fake_run(starting_agent, input):
        # Input zenginleştirilmiş olmalı
        assert "[BUSINESS_ID: biz_x]" in input
        assert "[PEER_REQUEST_FROM: sales_manager]" in input
        assert "Hangi reklamdan" in input
        return fake_result

    monkeypatch.setattr(pb.Runner, "run", fake_run)
    # Agent factory'yi de mock'la
    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        lambda: MagicMock(name="reklam_uzmani_agent"),
    )

    out = await pb._ask_reklam_uzmani_impl(
        "Hangi reklamdan en çok sıcak lead geldi?", "biz_x"
    )
    assert out["success"] is True
    assert out["source"] == "reklam_uzmani"
    assert "Slowdays" in out["answer"]
    assert out["business_id"] == "biz_x"


@pytest.mark.asyncio
async def test_business_id_whitespace_stripped(monkeypatch):
    fake_result = SimpleNamespace(final_output="OK")

    async def fake_run(starting_agent, input):
        assert "[BUSINESS_ID: biz_x]" in input  # stripped
        return fake_result

    monkeypatch.setattr(pb.Runner, "run", fake_run)
    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        lambda: MagicMock(),
    )

    out = await pb._ask_reklam_uzmani_impl("soru", "  biz_x  ")
    assert out["success"] is True


# ---------------------------------------------------------------------------
# Hata durumları
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout(monkeypatch):
    async def slow_run(starting_agent, input):
        await asyncio.sleep(5)
        return SimpleNamespace(final_output="never")

    monkeypatch.setattr(pb.Runner, "run", slow_run)
    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        lambda: MagicMock(),
    )

    out = await pb._ask_reklam_uzmani_impl(
        "soru", "biz_x", timeout_seconds=0.1
    )
    assert out["success"] is False
    assert "timeout" in out["error"]


@pytest.mark.asyncio
async def test_runner_exception(monkeypatch):
    async def boom(starting_agent, input):
        raise RuntimeError("openai down")

    monkeypatch.setattr(pb.Runner, "run", boom)
    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        lambda: MagicMock(),
    )

    out = await pb._ask_reklam_uzmani_impl("soru", "biz_x")
    assert out["success"] is False
    assert "openai down" in out["error"]


@pytest.mark.asyncio
async def test_empty_output(monkeypatch):
    fake_result = SimpleNamespace(final_output="")

    async def fake_run(starting_agent, input):
        return fake_result

    monkeypatch.setattr(pb.Runner, "run", fake_run)
    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        lambda: MagicMock(),
    )

    out = await pb._ask_reklam_uzmani_impl("soru", "biz_x")
    assert out["success"] is False
    assert "empty" in out["error"]


@pytest.mark.asyncio
async def test_agent_create_failure(monkeypatch):
    def boom_factory():
        raise RuntimeError("config missing")

    monkeypatch.setattr(
        "src.agents.sales.reklam_uzmani_agent.create_reklam_uzmani_agent",
        boom_factory,
    )

    out = await pb._ask_reklam_uzmani_impl("soru", "biz_x")
    assert out["success"] is False
    assert "config missing" in out["error"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_get_peer_bridge_tools_returns_ask_reklam_uzmani():
    tools = pb.get_peer_bridge_tools()
    assert len(tools) == 1
    assert tools[0].name == "ask_reklam_uzmani"
