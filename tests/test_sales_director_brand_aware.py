"""Sales Director brand identity prompt injection (auto_reply pattern mirror)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")


class TestBrandAwareInstructions:
    def test_no_env_returns_base_instructions(self, monkeypatch):
        monkeypatch.delenv("SALES_DIRECTOR_BUSINESS_ID", raising=False)
        from src.agents.sales.sales_manager_agent import _build_brand_aware_instructions
        base = "BASE INSTRUCTIONS HERE"
        assert _build_brand_aware_instructions(base) == base

    def test_brand_prepended_when_loaded(self, monkeypatch):
        monkeypatch.setenv("SALES_DIRECTOR_BUSINESS_ID", "biz1")
        # Patch the load_brand_identity function in the brand module — agent
        # imports it lazily via `from src.tools.brand import load_brand_identity`.
        bi = MagicMock()
        bi.prompt_summary.return_value = "MARKA: Slowdays, ton: samimi"

        import src.tools.brand as brand_mod
        monkeypatch.setattr(brand_mod, "load_brand_identity", lambda _bid: bi)

        from src.agents.sales.sales_manager_agent import _build_brand_aware_instructions
        out = _build_brand_aware_instructions("BASE")
        assert out.startswith("## BRAND CONTEXT")
        assert "Slowdays" in out
        assert out.endswith("BASE")

    def test_load_failure_falls_back_to_base(self, monkeypatch):
        monkeypatch.setenv("SALES_DIRECTOR_BUSINESS_ID", "biz1")
        import src.tools.brand as brand_mod

        def _boom(_bid):
            raise RuntimeError("firestore down")

        monkeypatch.setattr(brand_mod, "load_brand_identity", _boom)
        from src.agents.sales.sales_manager_agent import _build_brand_aware_instructions
        out = _build_brand_aware_instructions("BASE")
        assert out == "BASE"

    def test_director_instructions_alias_exported(self):
        from src.agents.instructions import (
            SALES_DIRECTOR_INSTRUCTIONS,
            SALES_MANAGER_INSTRUCTIONS,
        )
        assert SALES_DIRECTOR_INSTRUCTIONS is SALES_MANAGER_INSTRUCTIONS
        # Should mention 'Direktor' now
        assert "Direktoru" in SALES_DIRECTOR_INSTRUCTIONS or "Direktor" in SALES_DIRECTOR_INSTRUCTIONS
