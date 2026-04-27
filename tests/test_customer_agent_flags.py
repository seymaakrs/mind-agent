"""
CustomerAgentFlags testleri.

Davranış:
- Firestore settings/app_settings.customerAgent doc'undan okunur.
- Tüm bayraklar default False (güvenli varsayılan: kapalı).
- Eksik kolon → False (tolerant reader).
- Firestore hatası → tüm bayraklar False (sistem kırılmaz).
- enabled=False → diğer sub-flag'ler ne olursa olsun, "etkin" sayılmaz.
- Cache temizlenebilir (test/reload için).
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import patch

import pytest

from src.app.config import (
    CustomerAgentFlags,
    clear_customer_agent_flags_cache,
    get_customer_agent_flags,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Her testten önce cache temizle ki testler birbirine sızmasın."""
    clear_customer_agent_flags_cache()
    yield
    clear_customer_agent_flags_cache()


# ---------------------------------------------------------------------------
# Default davranış (Firestore boşken)
# ---------------------------------------------------------------------------


def test_all_flags_default_false_when_firestore_empty():
    """Firestore'da hiç customerAgent doc'u yoksa, hepsi False."""
    with patch("src.app.config._load_app_settings_from_firebase", return_value={}):
        flags = get_customer_agent_flags()
        assert flags.enabled is False
        assert flags.can_read_leads is False
        assert flags.can_read_pipeline is False
        assert flags.can_attach_reports is False
        assert flags.can_trigger_followup is False
        assert flags.can_post_for_lead is False


def test_all_flags_default_false_when_firestore_errors():
    """Firestore patlarsa default değerler döner, exception leak etmez."""
    with patch(
        "src.app.config._load_app_settings_from_firebase",
        side_effect=Exception("Firebase down"),
    ):
        flags = get_customer_agent_flags()
        assert flags.enabled is False
        assert flags.can_read_leads is False


# ---------------------------------------------------------------------------
# Firestore'dan okuma
# ---------------------------------------------------------------------------


def test_flags_read_from_firestore_camelcase():
    """Firestore camelCase alan adlarını snake_case'e map'ler."""
    fake_doc = {
        "customerAgent": {
            "enabled": True,
            "canReadLeads": True,
            "canReadPipeline": False,
            "canAttachReports": True,
            "canTriggerFollowup": False,
            "canPostForLead": False,
        }
    }
    with patch("src.app.config._load_app_settings_from_firebase", return_value=fake_doc):
        flags = get_customer_agent_flags()
        assert flags.enabled is True
        assert flags.can_read_leads is True
        assert flags.can_read_pipeline is False
        assert flags.can_attach_reports is True
        assert flags.can_trigger_followup is False


def test_partial_doc_missing_keys_default_false():
    """customerAgent doc'unda olmayan key'ler False kalır (tolerant reader)."""
    fake_doc = {
        "customerAgent": {
            "enabled": True,
            "canReadLeads": True,
            # Diğerleri eksik
        }
    }
    with patch("src.app.config._load_app_settings_from_firebase", return_value=fake_doc):
        flags = get_customer_agent_flags()
        assert flags.enabled is True
        assert flags.can_read_leads is True
        assert flags.can_attach_reports is False  # eksik → False


# ---------------------------------------------------------------------------
# is_capability_enabled — master flag mantığı
# ---------------------------------------------------------------------------


def test_capability_disabled_when_master_off():
    """enabled=False ise, alt-flag True olsa bile kapasite kapalı sayılır."""
    flags = CustomerAgentFlags(enabled=False, can_read_leads=True)
    assert flags.is_capability_enabled("can_read_leads") is False


def test_capability_enabled_when_master_and_subflag_on():
    """enabled=True + alt-flag=True → kapasite açık."""
    flags = CustomerAgentFlags(enabled=True, can_read_leads=True)
    assert flags.is_capability_enabled("can_read_leads") is True


def test_capability_disabled_when_master_on_but_subflag_off():
    """enabled=True ama alt-flag=False → kapasite kapalı."""
    flags = CustomerAgentFlags(enabled=True, can_read_leads=False)
    assert flags.is_capability_enabled("can_read_leads") is False


def test_capability_unknown_name_returns_false():
    """Bilinmeyen kapasite adı → False (yanlış kullanım sessizce kapanır)."""
    flags = CustomerAgentFlags(enabled=True)
    assert flags.is_capability_enabled("can_read_minds") is False


# ---------------------------------------------------------------------------
# Cache davranışı
# ---------------------------------------------------------------------------


def test_flags_cached_after_first_read():
    """get_customer_agent_flags ikinci çağrıda Firebase'e gitmez."""
    with patch(
        "src.app.config._load_app_settings_from_firebase",
        return_value={"customerAgent": {"enabled": True}},
    ) as mock_load:
        get_customer_agent_flags()
        get_customer_agent_flags()
        get_customer_agent_flags()
        assert mock_load.call_count == 1


def test_clear_cache_forces_reload():
    """clear_customer_agent_flags_cache() sonrası bir sonraki çağrı tekrar okur."""
    with patch(
        "src.app.config._load_app_settings_from_firebase",
        return_value={"customerAgent": {"enabled": True}},
    ) as mock_load:
        get_customer_agent_flags()
        clear_customer_agent_flags_cache()
        get_customer_agent_flags()
        assert mock_load.call_count == 2
