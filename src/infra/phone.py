"""E.164 phone normalization (TR-first).

Tek dogruluk: ayni telefon farkli formatlarda yazilirsa (05551234567,
905551234567, +90 555 123 45 67) lead dedupe icin tek bir kanonik
forma indirgenir. Aksi halde external_id'ler ayrilir, hayalet duplicate
lead'ler dogar.
"""
from __future__ import annotations


def _digits_and_plus(raw: str) -> str:
    out = []
    for i, c in enumerate(raw):
        if c.isdigit():
            out.append(c)
        elif c == "+" and i == 0:
            out.append(c)
    return "".join(out)


def normalize_phone_e164(raw: str | None, default_country: str = "TR") -> str | None:
    """Normalize a phone string to E.164. TR-only for now.

    Returns None for empty/garbage input so callers can skip writes.
    `default_country` is reserved for future expansion.
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = _digits_and_plus(raw.strip())
    if not cleaned:
        return None

    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if 11 <= len(digits) <= 15 and digits.isdigit():
            return f"+{digits}"
        return None

    if cleaned.startswith("00"):
        digits = cleaned[2:]
        if 11 <= len(digits) <= 15 and digits.isdigit():
            return f"+{digits}"
        return None

    if cleaned.startswith("90") and len(cleaned) == 12:
        return f"+{cleaned}"

    if cleaned.startswith("0") and len(cleaned) == 11:
        return f"+90{cleaned[1:]}"

    if len(cleaned) == 10 and cleaned.startswith("5"):
        return f"+90{cleaned}"

    return None


__all__ = ["normalize_phone_e164"]
