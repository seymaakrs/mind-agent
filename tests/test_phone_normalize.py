"""Tests for src/infra/phone.py — TR E.164 normalization."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.infra.phone import normalize_phone_e164


class TestNormalizePhoneE164:
    def test_none_input(self):
        assert normalize_phone_e164(None) is None

    def test_empty_string(self):
        assert normalize_phone_e164("") is None
        assert normalize_phone_e164("   ") is None

    def test_already_e164(self):
        assert normalize_phone_e164("+905551234567") == "+905551234567"

    def test_with_spaces(self):
        assert normalize_phone_e164("+90 555 123 45 67") == "+905551234567"

    def test_leading_zero_tr(self):
        assert normalize_phone_e164("05551234567") == "+905551234567"

    def test_country_no_plus(self):
        assert normalize_phone_e164("905551234567") == "+905551234567"

    def test_double_zero_prefix(self):
        assert normalize_phone_e164("00905551234567") == "+905551234567"

    def test_ten_digits_starting_5(self):
        assert normalize_phone_e164("5551234567") == "+905551234567"

    def test_garbage_returns_none(self):
        assert normalize_phone_e164("abcdef") is None
        assert normalize_phone_e164("123") is None

    def test_all_variants_canonical(self):
        canonical = "+905551234567"
        for raw in [
            "05551234567",
            "905551234567",
            "+905551234567",
            "+90 555 123 45 67",
            "0090 555 123 4567",
            "5551234567",
        ]:
            assert normalize_phone_e164(raw) == canonical, f"failed for {raw}"


class TestWebhookExternalIdDedup:
    def test_same_phone_different_format_same_external_id(self):
        from src.app.zernio_webhook import derive_external_id

        msg_a = {
            "platform": "whatsapp",
            "sender": {"id": "905551234567", "phoneNumber": "05551234567"},
        }
        msg_b = {
            "platform": "whatsapp",
            "sender": {"id": "905551234567", "phoneNumber": "+90 555 123 45 67"},
        }
        assert derive_external_id(msg_a) == derive_external_id(msg_b)

    def test_external_id_uses_normalized_phone(self):
        from src.app.zernio_webhook import derive_external_id

        msg = {
            "platform": "whatsapp",
            "sender": {"id": "x", "phoneNumber": "05551234567"},
        }
        ext = derive_external_id(msg)
        assert "+905551234567" in ext or "905551234567" in ext
