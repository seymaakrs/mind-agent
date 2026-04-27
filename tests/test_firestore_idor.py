"""
Firestore IDOR korumasi testleri.

Sorun (SECURITY_REPORT_TR.md Madde 2): get_document / save_document /
query_documents keyfi koleksiyon ve dokuman yolu kabul ediyordu. Servis
hesabi yetkili oldugu icin saldirgan settings/app_settings, baska bir
business'in verisi gibi her seye erisebilirdi.

Cozum: business_id REQUIRED. Path mutlaka 'businesses/{business_id}/...'
ile baslamali, subcollection whitelist'te olmali.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

import pytest

from src.tools.orchestrator.firestore import (
    ALLOWED_BUSINESS_SUBCOLLECTIONS,
    _validate_firestore_path,
)


# ---------------------------------------------------------------------------
# Mutlu yol — gecerli paths
# ---------------------------------------------------------------------------


def test_valid_business_subcollection_doc():
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path="businesses/biz_1/instagram_stats/week-2026-17",
        document_id=None,
        collection=None,
    )
    assert err is None


def test_valid_collection_id_form():
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=None,
        document_id="report_xyz",
        collection="businesses/biz_1/reports",
    )
    assert err is None


@pytest.mark.parametrize("sub", sorted(ALLOWED_BUSINESS_SUBCOLLECTIONS))
def test_each_allowed_subcollection_passes(sub):
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=f"businesses/biz_1/{sub}/some_doc",
        document_id=None,
        collection=None,
    )
    assert err is None, f"Subcollection {sub} reddedildi: {err}"


# ---------------------------------------------------------------------------
# Cross-tenant — baska business'in verisine ulasma
# ---------------------------------------------------------------------------


def test_cross_business_path_rejected():
    """biz_1 olarak login + biz_2'nin verisine erismek istegi → PERMISSION_DENIED."""
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path="businesses/biz_2/reports/sensitive",
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] == "PERMISSION_DENIED"


def test_cross_business_collection_form_rejected():
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=None,
        document_id="doc",
        collection="businesses/biz_2/reports",
    )
    assert err is not None
    assert err["error_code"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Top-level (non-business) — settings, users, errors keyfi reddedilir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_path",
    [
        "settings/app_settings",
        "users/admin",
        "errors/some_id",
        "documents/leaked",
    ],
)
def test_non_business_root_rejected(bad_path):
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=bad_path,
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Subcollection whitelist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_sub",
    ["secrets", "private", "credentials", "config", "users"],
)
def test_unknown_subcollection_rejected(bad_sub):
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=f"businesses/biz_1/{bad_sub}/x",
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] == "PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Path traversal / format / business_id sanity
# ---------------------------------------------------------------------------


def test_path_traversal_in_business_id_rejected():
    err = _validate_firestore_path(
        business_id="../other",
        document_path="businesses/../other/data/x",
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] in ("INVALID_INPUT", "PERMISSION_DENIED")


def test_empty_business_id_rejected():
    err = _validate_firestore_path(
        business_id="",
        document_path="businesses//reports/x",
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] == "INVALID_INPUT"


def test_odd_segment_count_rejected():
    """Firestore: collection ve document alternasyonu — tek sayilarda doc_id eksik."""
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path="businesses/biz_1/reports",  # 3 segment, doc_id yok
        document_id=None,
        collection=None,
    )
    assert err is not None
    assert err["error_code"] == "INVALID_INPUT"


def test_no_document_id_rejected():
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path=None,
        document_id=None,
        collection="businesses/biz_1/reports",
    )
    assert err is not None
    assert err["error_code"] == "INVALID_INPUT"


def test_special_chars_in_segment_rejected():
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path="businesses/biz_1/reports/../escape",
        document_id=None,
        collection=None,
    )
    assert err is not None


# ---------------------------------------------------------------------------
# Hem path hem de id verilirse — path oncelikli (mevcut davranis korunur)
# ---------------------------------------------------------------------------


def test_path_takes_precedence_over_id():
    """document_path verilirse, document_id ve collection ignore edilir."""
    err = _validate_firestore_path(
        business_id="biz_1",
        document_path="businesses/biz_1/reports/r1",
        document_id="ignored_id",
        collection="businesses/biz_2/secrets",  # path varsa bu hicbir sey ifade etmez
    )
    assert err is None
