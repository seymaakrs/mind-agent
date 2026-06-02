"""Tests for cleanup_fake_leads.py — sahte lead temizlik mantigi (Adim 3).

Silme kriterleri + Etkilesimler baglanti tespiti pure fonksiyonlar olarak
test edilir. Network yok.
"""
from __future__ import annotations

from scripts.cleanup_fake_leads import (
    classify_reason,
    detect_etk_link_field,
    is_fake_lead,
)


class TestIsFakeLead:
    def test_zernio_webhook_source_is_fake(self):
        assert is_fake_lead({"source_workflow_id": "mind_agent_zernio_webhook"})

    def test_unknown_name_is_fake(self):
        assert is_fake_lead({"ad_soyad": "Unknown"})
        assert is_fake_lead({"ad_soyad": "  unknown  "})  # bosluk/kucuk harf

    def test_test_token_in_notlar(self):
        assert is_fake_lead({"notlar": "bu bir TEST kaydidir"})

    def test_test_token_in_external_id(self):
        assert is_fake_lead({"external_id": "test-123"})
        assert is_fake_lead({"external_event_id": "abc_TEST"})

    def test_real_lead_not_fake(self):
        row = {
            "source_workflow_id": "outreach_agent_v1",
            "ad_soyad": "Ayse Yilmaz",
            "notlar": "Bodrum oteli, ilgileniyor",
            "external_id": "wamid.XYZ",
        }
        assert not is_fake_lead(row)

    def test_empty_row_not_fake(self):
        assert not is_fake_lead({})

    def test_name_containing_unknown_substring_not_fake(self):
        # 'Unknown Corp' gibi gercek bir isim yanlislikla silinmemeli
        assert not is_fake_lead({"ad_soyad": "Unknown Corp Ltd"})


class TestClassifyReason:
    def test_lists_all_matching_reasons(self):
        row = {
            "source_workflow_id": "mind_agent_zernio_webhook",
            "ad_soyad": "Unknown",
            "notlar": "test",
        }
        reason = classify_reason(row)
        assert "mind_agent_zernio_webhook" in reason
        assert "Unknown" in reason
        assert "test" in reason

    def test_single_reason(self):
        assert "Unknown" in classify_reason({"ad_soyad": "Unknown"})


class TestDetectEtkLinkField:
    def test_detects_plain_lead_id(self):
        etk = [{"Id": 1, "lead_id": 10}, {"Id": 2, "lead_id": 11}]
        assert detect_etk_link_field(etk, {10, 11}) == "lead_id"

    def test_detects_link_object_form(self):
        etk = [{"Id": 1, "Leadler": {"Id": 10}}]
        assert detect_etk_link_field(etk, {10}) == "Leadler"

    def test_returns_none_when_no_match(self):
        etk = [{"Id": 1, "baska_alan": 999}]
        assert detect_etk_link_field(etk, {10, 11}) is None

    def test_empty_inputs(self):
        assert detect_etk_link_field([], {10}) is None
        assert detect_etk_link_field([{"Id": 1, "lead_id": 10}], set()) is None
