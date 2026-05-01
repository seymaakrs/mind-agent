"""NocoDB schema contract test.

Verifies that the live NocoDB instance matches the contract defined in
`customer_agent/docs/NOCODB-SCHEMA-V2.md`. If a column is renamed, removed,
or its uniqueness changes, this test fails — preventing silent breakage of
n8n workflows and mind-agent code that depend on the schema.

Field names are Turkish to match `src/tools/sales/nocodb_tools.py`.

Skipped automatically when NocoDB credentials are not configured (e.g. in
local dev or CI without secrets) so it does not block the existing 87-test
suite.

Run manually:
    NOCODB_BASE_URL=... NOCODB_API_TOKEN_READ=... \\
    NOCODB_LEADS_TABLE_ID=... NOCODB_MESSAGES_TABLE_ID=... \\
    NOCODB_NOTIFICATIONS_TABLE_ID=... \\
    pytest tests/test_nocodb_schema_contract.py -v
"""
from __future__ import annotations

import os
from typing import Any

import pytest

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


# Expected schema — mirrors customer_agent/docs/NOCODB-SCHEMA-V2.md
# Beyza'nin canli production schemasi (Leadler + Etkilesimler).
EXPECTED_LEADS = {
    "required": {
        "ad_soyad", "kaynak", "asama",
    },
    "optional": {
        "external_id", "leadgen_id", "source_workflow_id",
        "email", "telefon", "sirket_adi", "pozisyon", "sektor",
        "konum", "web_sitesi", "instagram", "linkedin_url",
        "google_puani", "lead_skoru", "ihtiyac_notu",
        "atanan_kisi", "notlar",
    },
    "unique": {"external_id", "leadgen_id"},
}

EXPECTED_LEAD_MESSAGES = {
    "required": {
        "lead_adi", "tarih", "kanal", "yon",
        "mesaj_icerigi", "otomatik_mi",
    },
    "optional": {
        "external_message_id", "tur", "sonuc", "agent", "notlar",
    },
    "unique": {"external_message_id"},
}

TABLES = {
    "Leadler": ("NOCODB_LEADS_TABLE_ID", EXPECTED_LEADS),
    "Etkilesimler": ("NOCODB_MESSAGES_TABLE_ID", EXPECTED_LEAD_MESSAGES),
}

# NocoDB system columns that should be tolerated as "extra"
SYSTEM_COLUMNS = {
    "Id", "id", "ID", "CreatedAt", "UpdatedAt", "ncRecordId", "ncRecordHash",
    "nc_created_by", "nc_updated_by",
}


def _nocodb_configured() -> bool:
    if httpx is None:
        return False
    if not os.getenv("NOCODB_BASE_URL"):
        return False
    if not (os.getenv("NOCODB_API_TOKEN_READ") or os.getenv("NOCODB_API_TOKEN")):
        return False
    return all(os.getenv(env) for env, _ in TABLES.values())


# Etkilesimler tablosu hem mesajlar hem bildirimler icin ortak kullaniliyor
# (notify_seyma 'tur=bildirim' satiri yaziyor). Bu yuzden seyma_notifications
# ayri tablo yok — kontract test sadece Leadler + Etkilesimler kapsiyor.


pytestmark = pytest.mark.skipif(
    not _nocodb_configured(),
    reason="NocoDB credentials not set; skipping schema contract test.",
)


def _fetch_table_meta(table_id: str) -> dict[str, Any]:
    base = os.environ["NOCODB_BASE_URL"].rstrip("/")
    token = os.getenv("NOCODB_API_TOKEN_READ") or os.environ["NOCODB_API_TOKEN"]
    url = f"{base}/api/v2/meta/tables/{table_id}"
    resp = httpx.get(url, headers={"xc-token": token}, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def _column_names(meta: dict[str, Any]) -> set[str]:
    return {col["title"] for col in meta.get("columns", [])}


def _unique_column_names(meta: dict[str, Any]) -> set[str]:
    return {
        col["title"]
        for col in meta.get("columns", [])
        if col.get("unique") or col.get("uidt") == "ID"
    }


@pytest.mark.parametrize("table_name", list(TABLES.keys()))
def test_table_has_required_columns(table_name: str) -> None:
    env_var, expected = TABLES[table_name]
    meta = _fetch_table_meta(os.environ[env_var])
    actual = _column_names(meta)
    missing = expected["required"] - actual
    assert not missing, (
        f"NocoDB table '{table_name}' is missing required columns: {missing}. "
        f"Update NOCODB-SCHEMA-V2.md or add the columns in NocoDB UI."
    )


@pytest.mark.parametrize("table_name", list(TABLES.keys()))
def test_table_has_no_unexpected_extra_columns(table_name: str) -> None:
    env_var, expected = TABLES[table_name]
    meta = _fetch_table_meta(os.environ[env_var])
    actual = _column_names(meta)
    known = expected["required"] | expected["optional"] | SYSTEM_COLUMNS
    extras = actual - known
    assert not extras, (
        f"NocoDB table '{table_name}' has columns not in NOCODB-SCHEMA-V2.md: {extras}. "
        f"Either document them in the schema or remove from NocoDB."
    )


@pytest.mark.parametrize("table_name", list(TABLES.keys()))
def test_unique_constraints_match(table_name: str) -> None:
    env_var, expected = TABLES[table_name]
    if not expected["unique"]:
        pytest.skip(f"No unique constraints expected for {table_name}")
    meta = _fetch_table_meta(os.environ[env_var])
    unique_actual = _unique_column_names(meta)
    missing_unique = expected["unique"] - unique_actual
    assert not missing_unique, (
        f"NocoDB table '{table_name}' missing UNIQUE on: {missing_unique}. "
        f"Idempotency will be broken — n8n retries will create duplicates."
    )
