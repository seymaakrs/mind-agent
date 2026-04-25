"""
get_instagram_insights / get_post_analytics — ownership check (IDOR koruma).

Sorun (SECURITY_REPORT_TR.md Madde 4): paylasilan Late API key tum profillere
erisebildiginden, baska bir business'in late_profile_id'si verilirse onun
metriklerini sizdiriyordu.

Cozum: business_id artik zorunlu. Tool Firestore'dan businesses/{bid}.
late_profile_id'yi okur ve caller'in verdigi (varsa) bununla eslesmiyorsa
PERMISSION_DENIED doner. late_profile_id verilmediyse Firestore'dan alinir.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.instagram_tools import (
    _check_late_profile_ownership,
)


def _mock_business_doc_client(business_data: dict | None):
    """Firestore document_client mock'i - get_document() bu data'yi doner."""
    fake_client = MagicMock()
    fake_client.get_document = MagicMock(return_value=business_data)
    return fake_client


# ---------------------------------------------------------------------------
# _check_late_profile_ownership — pure logic
# ---------------------------------------------------------------------------


def test_returns_effective_profile_id_when_no_caller_value():
    """late_profile_id verilmediyse → Firestore'daki ID kullanilir."""
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=_mock_business_doc_client({"late_profile_id": "lp_real"}),
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_1",
            caller_late_profile_id=None,
        )
    assert ok is True
    assert value == "lp_real"


def test_accepts_matching_profile_id():
    """Caller dogru late_profile_id verdiyse → kabul, ayni ID donulur."""
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=_mock_business_doc_client({"late_profile_id": "lp_real"}),
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_1",
            caller_late_profile_id="lp_real",
        )
    assert ok is True
    assert value == "lp_real"


def test_rejects_mismatching_profile_id():
    """Caller baska business'in late_profile_id'sini gecirdiyse → reddedilir."""
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=_mock_business_doc_client({"late_profile_id": "lp_real"}),
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_1",
            caller_late_profile_id="lp_other_business",
        )
    assert ok is False
    assert isinstance(value, dict)
    assert value["success"] is False
    assert value["error_code"] == "PERMISSION_DENIED"


def test_rejects_when_business_not_found():
    """Firestore'da business yok → NOT_FOUND."""
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=_mock_business_doc_client(None),
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_unknown",
            caller_late_profile_id=None,
        )
    assert ok is False
    assert isinstance(value, dict)
    assert value["error_code"] == "NOT_FOUND"


def test_rejects_when_business_has_no_late_profile_id():
    """Business var ama late_profile_id alani yok → INVALID_INPUT."""
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=_mock_business_doc_client({"name": "Test", "late_profile_id": ""}),
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_1",
            caller_late_profile_id=None,
        )
    assert ok is False
    assert isinstance(value, dict)
    assert value["error_code"] == "INVALID_INPUT"


def test_business_id_empty_rejected():
    """business_id bos string → INVALID_INPUT (Firestore'a bile gitmez)."""
    ok, value = _check_late_profile_ownership(
        business_id="",
        caller_late_profile_id="lp_x",
    )
    assert ok is False
    assert isinstance(value, dict)
    assert value["error_code"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Firestore hatasi durumu — tool'in genel davranisina degmesin
# ---------------------------------------------------------------------------


def test_firestore_exception_returns_service_error():
    """Firestore patlarsa tool patlamaz, SERVICE_ERROR doner."""
    fake_client = MagicMock()
    fake_client.get_document = MagicMock(side_effect=Exception("firestore down"))
    with patch(
        "src.tools.instagram_tools.get_document_client",
        return_value=fake_client,
    ):
        ok, value = _check_late_profile_ownership(
            business_id="biz_1",
            caller_late_profile_id=None,
        )
    assert ok is False
    assert isinstance(value, dict)
    assert value["error_code"] == "SERVER_ERROR"
