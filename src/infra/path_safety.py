"""
Path safety helpers — kullanici tarafindan kontrol edilen string'leri
dosya/dizin yolu bileseni olarak kullanmadan once dogrular.

Path traversal (../..), separator injection (/, \\), null byte ve diger
ozel karakterleri reddeder. Storage backend'i (Firebase Storage / GCS)
nesne deposu olsa da '../' iceren bir nesne yolu, baska bir business'in
verisinin uzerine yazilmasina yol acabilir.

SECURITY_REPORT_TR.md Madde 6.
"""
from __future__ import annotations

import re

# WHITELIST: yalniz alfanumerik + dot + dash + underscore izinli.
# Bunun disindaki tum karakterler (separator, bosluk, null, kontrol, vs.)
# reddedilir.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

DEFAULT_MAX_LENGTH = 128


def safe_path_segment(value: object, *, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """
    Tek bir path bilesenini (filename veya directory adi) dogrular.

    Args:
        value: Dogrulanacak deger (string olmali).
        max_length: Izin verilen maksimum karakter sayisi.

    Returns:
        Validated string (input ile aynen ayni; sanitize ETMEZ — reddeder).

    Raises:
        ValueError: Deger gecersizse (acik mesajla).
    """
    if not isinstance(value, str):
        raise ValueError(
            f"Path segment must be a string; got {type(value).__name__}."
        )
    if not value:
        raise ValueError("Path segment cannot be empty.")
    if len(value) > max_length:
        raise ValueError(
            f"Path segment too long (max {max_length} chars, got {len(value)})."
        )
    if value == ".":
        raise ValueError("Path segment cannot be '.' (current directory reference).")
    # Defansif: '..' substring her durumda reddet — meşru bir filename'da
    # neredeyse hiç kullanılmaz (a..b gibi); reddetmek false-positive maliyetinden
    # daha guvenli.
    if ".." in value:
        raise ValueError(
            f"Path segment cannot contain '..' (path traversal attempt): {value!r}"
        )
    if not _SAFE_SEGMENT_RE.match(value):
        raise ValueError(
            f"Path segment contains invalid characters (allowed: A-Z a-z 0-9 . _ -): {value!r}"
        )
    return value


__all__ = ["safe_path_segment", "DEFAULT_MAX_LENGTH"]
