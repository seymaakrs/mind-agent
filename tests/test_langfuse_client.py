"""Tests for src.infra.langfuse_client — graceful degradation wiring."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.app.config import Settings, get_settings
from src.infra import langfuse_client


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test starts with fresh init state and clean settings cache."""
    langfuse_client._reset_for_tests()
    get_settings.cache_clear()
    yield
    langfuse_client._reset_for_tests()
    get_settings.cache_clear()


def _stub_settings(public: str | None, secret: str | None) -> Settings:
    return Settings.model_validate(
        {
            "openai_api_key": "sk-test",
            "langfuse_public_key": public,
            "langfuse_secret_key": secret,
            "langfuse_host": "https://cloud.langfuse.com",
        }
    )


def test_start_skips_when_keys_missing(caplog):
    """No keys → init returns False, agent calismasi etkilenmez."""
    with patch.object(langfuse_client, "get_settings", return_value=_stub_settings(None, None)):
        assert langfuse_client.start_langfuse() is False
        assert langfuse_client.is_initialized() is False
    assert any("Langfuse anahtarlari yok" in r.message for r in caplog.records)


def test_start_skips_when_only_public_key():
    """Yarim konfig (sadece public) → init skip eder."""
    with patch.object(
        langfuse_client, "get_settings", return_value=_stub_settings("pk-lf-test", None)
    ):
        assert langfuse_client.start_langfuse() is False


def test_start_is_idempotent():
    """Initialized iken ikinci cagri no-op True doner."""
    langfuse_client._initialized = True
    assert langfuse_client.start_langfuse() is True


def test_flush_noop_when_not_initialized():
    """Init edilmediyse flush sessizce gecer."""
    assert langfuse_client.is_initialized() is False
    langfuse_client.flush_langfuse()  # should not raise


def test_start_handles_missing_instrumentation_package(caplog):
    """openinference paketi yoksa graceful skip."""
    with patch.object(
        langfuse_client, "get_settings",
        return_value=_stub_settings("pk-lf-test", "sk-lf-test"),
    ):
        with patch.dict(
            "sys.modules",
            {"openinference.instrumentation.openai_agents": None},
        ):
            # Force ImportError via sys.modules None trick
            import sys
            sys.modules.pop("openinference.instrumentation.openai_agents", None)
            with patch(
                "builtins.__import__",
                side_effect=ImportError("simulated missing package"),
            ):
                assert langfuse_client.start_langfuse() is False
                assert langfuse_client.is_initialized() is False


def test_start_sets_env_vars_when_keys_present():
    """Anahtarlar varsa Langfuse SDK env var'lari set edilmeli."""
    # Save & clear env to test setdefault behavior
    for var in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        os.environ.pop(var, None)

    with patch.object(
        langfuse_client, "get_settings",
        return_value=_stub_settings("pk-lf-test", "sk-lf-test"),
    ):
        # Mock the instrumentor so we don't actually try to connect
        import sys
        from unittest.mock import MagicMock
        fake_module = MagicMock()
        sys.modules["openinference.instrumentation.openai_agents"] = fake_module
        try:
            langfuse_client.start_langfuse()
            assert os.environ.get("LANGFUSE_PUBLIC_KEY") == "pk-lf-test"
            assert os.environ.get("LANGFUSE_SECRET_KEY") == "sk-lf-test"
            assert os.environ.get("LANGFUSE_HOST") == "https://cloud.langfuse.com"
        finally:
            sys.modules.pop("openinference.instrumentation.openai_agents", None)
            for var in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
                os.environ.pop(var, None)


def test_config_exposes_langfuse_fields():
    """Settings sinifinda 3 Langfuse alani var ve LANGFUSE_HOST default cloud."""
    s = Settings.model_validate({"openai_api_key": "sk-test"})
    assert hasattr(s, "langfuse_public_key")
    assert hasattr(s, "langfuse_secret_key")
    assert s.langfuse_host == "https://cloud.langfuse.com"
    assert s.langfuse_public_key is None
    assert s.langfuse_secret_key is None
