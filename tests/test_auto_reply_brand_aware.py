"""Tests for brand_identity wiring into Auto-reply Agent (Faz C completion)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.auto_reply.policy import AutoReplyConfig  # noqa: E402
from src.agents.auto_reply.responder import (  # noqa: E402
    AutoReplyDecision,
    decide_reply,
)
from src.agents.auto_reply import runner  # noqa: E402


class TestAutoReplyBrandConfig:
    def test_brand_defaults(self):
        c = AutoReplyConfig()
        assert c.business_id == ""
        assert c.enable_brand_aware is True

    def test_brand_env_overrides(self, monkeypatch):
        monkeypatch.setenv("AUTO_REPLY_BUSINESS_ID", "slowdays")
        monkeypatch.setenv("AUTO_REPLY_BRAND_AWARE", "false")
        c = AutoReplyConfig.from_env()
        assert c.business_id == "slowdays"
        assert c.enable_brand_aware is False

    def test_brand_aware_truthy_values(self, monkeypatch):
        for v in ("1", "true", "True", "yes"):
            monkeypatch.setenv("AUTO_REPLY_BRAND_AWARE", v)
            assert AutoReplyConfig.from_env().enable_brand_aware is True
        for v in ("0", "false", "no", "False"):
            monkeypatch.setenv("AUTO_REPLY_BRAND_AWARE", v)
            assert AutoReplyConfig.from_env().enable_brand_aware is False


class TestDecideReplyBrandPrompt:
    @pytest.mark.asyncio
    async def test_brand_prompt_none_backward_compat(self, monkeypatch):
        captured = {}

        async def fake_run(*, starting_agent, input):
            captured["instructions"] = starting_agent.instructions
            captured["input"] = input
            res = MagicMock()
            res.final_output = AutoReplyDecision(
                intent="olumlu", reply_text="ok", confidence=0.9
            )
            return res

        from src.agents.auto_reply import responder
        monkeypatch.setattr(responder.Runner, "run", fake_run)
        out = await decide_reply("merhaba", brand_prompt=None)
        assert out.intent == "olumlu"
        assert "BRAND CONTEXT" not in captured["instructions"]

    @pytest.mark.asyncio
    async def test_brand_prompt_injected_into_instructions(self, monkeypatch):
        captured = {}

        async def fake_run(*, starting_agent, input):
            captured["instructions"] = starting_agent.instructions
            res = MagicMock()
            res.final_output = AutoReplyDecision(
                intent="olumlu", reply_text="ok", confidence=0.9
            )
            return res

        from src.agents.auto_reply import responder
        monkeypatch.setattr(responder.Runner, "run", fake_run)
        await decide_reply(
            "merhaba",
            brand_prompt="VOICE: warm, casual; AVOID: corporate jargon",
        )
        assert "BRAND CONTEXT" in captured["instructions"]
        assert "VOICE: warm, casual" in captured["instructions"]
        assert "AVOID: corporate jargon" in captured["instructions"]


class TestRunnerBrandLoading:
    @pytest.mark.asyncio
    async def test_loop_loads_brand_when_business_id_set(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")

        bi = MagicMock()
        bi.prompt_summary.return_value = "VOICE: friendly, TR"
        load_calls = []

        def fake_load(business_id):
            load_calls.append(business_id)
            return bi

        import src.tools.brand as brand_mod
        monkeypatch.setattr(brand_mod, "load_brand_identity", fake_load)

        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(
            runner, "find_pending_inbounds", lambda *a, **k: []
        )

        captured_brand = {}

        original_handle = runner.handle_one

        async def spy_handle(**kwargs):
            captured_brand["brand_prompt"] = kwargs.get("brand_prompt")
            return {"row_id": 1}

        monkeypatch.setattr(runner, "handle_one", spy_handle)

        cfg = AutoReplyConfig(business_id="slowdays", enable_brand_aware=True)
        await runner.loop(cfg, max_iterations=1)

        assert load_calls == ["slowdays"]

    @pytest.mark.asyncio
    async def test_loop_passes_brand_prompt_to_handle_one(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")

        bi = MagicMock()
        bi.prompt_summary.return_value = "VOICE: friendly"

        import src.tools.brand as brand_mod
        monkeypatch.setattr(brand_mod, "load_brand_identity", lambda b: bi)

        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(
            runner, "find_pending_inbounds",
            lambda *a, **k: [{"Id": 7, "mesaj_icerigi": "hi", "lead_adi": "X"}],
        )

        captured = {}

        async def spy_handle(**kwargs):
            captured["brand_prompt"] = kwargs.get("brand_prompt")
            return {"row_id": 7}

        monkeypatch.setattr(runner, "handle_one", spy_handle)

        import asyncio as _aio
        async def no_sleep(*a, **k): return None
        monkeypatch.setattr(_aio, "sleep", no_sleep)

        cfg = AutoReplyConfig(business_id="slowdays", enable_brand_aware=True)
        await runner.loop(cfg, max_iterations=1)

        assert captured["brand_prompt"] == "VOICE: friendly"

    @pytest.mark.asyncio
    async def test_loop_no_brand_when_disabled(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")

        load_calls = []
        import src.tools.brand as brand_mod
        monkeypatch.setattr(
            brand_mod, "load_brand_identity",
            lambda b: load_calls.append(b) or MagicMock(),
        )

        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(runner, "find_pending_inbounds", lambda *a, **k: [])

        cfg = AutoReplyConfig(business_id="slowdays", enable_brand_aware=False)
        await runner.loop(cfg, max_iterations=1)
        assert load_calls == []

    @pytest.mark.asyncio
    async def test_loop_continues_when_brand_load_raises(self, monkeypatch):
        monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")

        def boom(b):
            raise RuntimeError("firestore down")

        import src.tools.brand as brand_mod
        monkeypatch.setattr(brand_mod, "load_brand_identity", boom)

        nocodb = MagicMock()
        monkeypatch.setattr(runner, "get_nocodb_client", lambda: nocodb)
        monkeypatch.setattr(
            runner, "find_pending_inbounds",
            lambda *a, **k: [{"Id": 1, "mesaj_icerigi": "hi", "lead_adi": "X"}],
        )

        captured = {}

        async def spy_handle(**kwargs):
            captured["brand_prompt"] = kwargs.get("brand_prompt")
            return {"row_id": 1}

        monkeypatch.setattr(runner, "handle_one", spy_handle)

        import asyncio as _aio
        async def no_sleep(*a, **k): return None
        monkeypatch.setattr(_aio, "sleep", no_sleep)

        cfg = AutoReplyConfig(business_id="slowdays", enable_brand_aware=True)
        await runner.loop(cfg, max_iterations=1)
        assert captured["brand_prompt"] is None
