"""
image_tools path traversal koruma testleri.

Strateji: validation logic'ini sade bir helper'a (_validate_image_path_inputs)
cikariyoruz; bu fonksiyonu dogrudan test ediyoruz. Tool'un kendi gercek async
yolu @function_tool decorator'iyle sarildigi icin in-process inspection guc;
helper'i test etmek davranis aciklamasi acisindan yeterli ve yeterince saglam.

SECURITY_REPORT_TR.md Madde 6.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

import pytest

from src.tools.image_tools import _validate_image_path_inputs


# ---------------------------------------------------------------------------
# Mutlu yol — gecerli inputlar None doner (geciste serbest)
# ---------------------------------------------------------------------------


def test_valid_inputs_return_none():
    err = _validate_image_path_inputs(
        file_name="logo.png",
        business_id="abc123",
        source_file_path=None,
    )
    assert err is None


def test_valid_inputs_with_source_path_return_none():
    err = _validate_image_path_inputs(
        file_name="scene_01.jpg",
        business_id="biz_001",
        source_file_path="images/biz_001/logo.png",
    )
    assert err is None


def test_business_id_optional():
    err = _validate_image_path_inputs(
        file_name="ok.png",
        business_id=None,
        source_file_path=None,
    )
    assert err is None


# ---------------------------------------------------------------------------
# Path traversal — file_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    ["../etc/passwd", "..\\windows", "..", "a..b.png", "name../ext"],
)
def test_traversal_in_file_name_returns_error(bad_name):
    err = _validate_image_path_inputs(
        file_name=bad_name,
        business_id="abc",
        source_file_path=None,
    )
    assert err is not None
    assert err["success"] is False
    assert err["error_code"] == "INVALID_INPUT"
    assert "file_name" in err["error"]


# ---------------------------------------------------------------------------
# Path traversal — business_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    ["../other_business", "..", "a/b", "a\\b", "abc..def"],
)
def test_traversal_in_business_id_returns_error(bad_id):
    err = _validate_image_path_inputs(
        file_name="ok.png",
        business_id=bad_id,
        source_file_path=None,
    )
    assert err is not None
    assert err["success"] is False
    assert err["error_code"] == "INVALID_INPUT"
    assert "business_id" in err["error"]


# ---------------------------------------------------------------------------
# Path traversal — source_file_path (multi-segment, '..' her segmentte yasak)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_path",
    [
        "../../etc/passwd",
        "images/../secrets/key.json",
        "images/abc/../../escape.png",
        "/abs/path",
        "a\\b\\c.png",
    ],
)
def test_traversal_in_source_file_path_returns_error(bad_path):
    err = _validate_image_path_inputs(
        file_name="ok.png",
        business_id="abc",
        source_file_path=bad_path,
    )
    assert err is not None
    assert err["success"] is False
    assert err["error_code"] == "INVALID_INPUT"
    assert "source_file_path" in err["error"]


def test_legitimate_source_file_path_ok():
    """Gecerli multi-segment path (her segment safe): kabul."""
    err = _validate_image_path_inputs(
        file_name="ok.png",
        business_id="abc",
        source_file_path="images/abc/logo.png",
    )
    assert err is None
