"""
Path safety helper testleri.

safe_path_segment(): tek bir path bilesenini (filename, dizin adi) dogrular.
Path traversal ('..'), separator karakterleri ('/' ve '\\'), null byte ve
diger tehlikeli karakterleri reddeder.

SECURITY_REPORT_TR.md Madde 6 (Path Traversal) icin temel.
"""
from __future__ import annotations

import pytest

from src.infra.path_safety import safe_path_segment


# ---------------------------------------------------------------------------
# Mutlu yol — yaygin gecerli isimler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "image.png",
        "logo_2024.jpg",
        "abc-def_123",
        "a.b.c",  # birden fazla nokta tek basina sorun degil
        "X",
        "scene_01.png",
        "MyFile-2024.jpeg",
    ],
)
def test_valid_segments_pass(value):
    assert safe_path_segment(value) == value


# ---------------------------------------------------------------------------
# Path traversal — '..' her durumda reddedilir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "..",
        "...",  # spec: '..' substring yasak (defansif)
        "../etc/passwd",
        "..\\windows\\system32",
        "foo/../bar",
        "a..b",
        "..hidden",
        "name..ext",
    ],
)
def test_traversal_attempts_rejected(value):
    with pytest.raises(ValueError, match="(traversal|invalid)"):
        safe_path_segment(value)


# ---------------------------------------------------------------------------
# Separator karakterleri — '/' ve '\\' reddedilir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "a/b",
        "/abs",
        "abs/",
        "a\\b",
        "C:\\file",
    ],
)
def test_separators_rejected(value):
    with pytest.raises(ValueError, match="invalid"):
        safe_path_segment(value)


# ---------------------------------------------------------------------------
# Diger gecersiz karakterler — null byte, bosluk, kontrol vs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "a\x00b",  # null byte
        "a b",  # bosluk
        "a;b",  # noktali virgul
        "a|b",  # pipe
        "a$b",
        "a&b",
        "a(b",
        "a*b",
        "a?b",
        "a<b",
        "a>b",
        '"quote"',
        "a'b",
        "a\nb",  # newline
        "a\tb",  # tab
    ],
)
def test_special_chars_rejected(value):
    with pytest.raises(ValueError, match="invalid"):
        safe_path_segment(value)


# ---------------------------------------------------------------------------
# Bos / sadece nokta degerleri
# ---------------------------------------------------------------------------


def test_empty_rejected():
    with pytest.raises(ValueError, match="empty"):
        safe_path_segment("")


def test_only_dot_rejected():
    """Sadece '.' segment current-directory referansi, yasak."""
    with pytest.raises(ValueError):
        safe_path_segment(".")


def test_non_string_rejected():
    """String olmayan input'lar reddedilir (mypy/runtime savunma)."""
    with pytest.raises(ValueError, match="string"):
        safe_path_segment(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Uzunluk siniri
# ---------------------------------------------------------------------------


def test_max_length_default_enforced():
    long_name = "a" * 129
    with pytest.raises(ValueError, match="long"):
        safe_path_segment(long_name)


def test_custom_max_length():
    safe_path_segment("abc", max_length=3)
    with pytest.raises(ValueError, match="long"):
        safe_path_segment("abcd", max_length=3)


def test_just_under_limit_ok():
    safe_path_segment("a" * 128)
