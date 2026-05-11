"""NocoDB schema migration for Adim 8 (Guardian / Bekci Robot).

Iki mod:

A) ``NOCODB_SETTINGS_TABLE_ID`` SET ise: o tabloya 7 kolon ekler + initial
   row insert eder (idempotent, mevcut sutunlari atlar).

B) ``NOCODB_SETTINGS_TABLE_ID`` BOSSA ama ``NOCODB_LEADS_TABLE_ID`` SET ise:
   Leadler tablosunun meta'sindan ``base_id``yi cikarir, ``system_settings``
   tablosunu olusturur (NocoDB v2 meta API), kolonlari ekler ve initial row
   insert eder. Yeni table_id'yi STDOUT'a yazar — kullanıcı Cloud Run env'ine
   eklemeli (``NOCODB_SETTINGS_TABLE_ID=...``).

Run (Cloud Shell):
    export NOCODB_BASE_URL=...
    export NOCODB_API_TOKEN=...
    # Mod A icin:
    export NOCODB_SETTINGS_TABLE_ID=...
    # YA DA Mod B icin (table'i benim yaratmam):
    export NOCODB_LEADS_TABLE_ID=...
    python scripts/migrate_guardian_schema.py
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx


_TIMEOUT = 30.0
_TABLE_NAME = "system_settings"


def _client(base_url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"xc-token": token, "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )


def _get_base_id_from_table(client: httpx.Client, table_id: str) -> str:
    """Mevcut bir tablonun meta'sindan base_id'yi çıkar."""
    r = client.get(f"/api/v2/meta/tables/{table_id}")
    r.raise_for_status()
    meta = r.json()
    base_id = (
        meta.get("base_id")
        or meta.get("baseId")
        or meta.get("source_id")
        or meta.get("sourceId")
    )
    if not base_id:
        raise RuntimeError(
            f"could not extract base_id from table {table_id}; meta keys: "
            f"{list(meta.keys())[:20]}"
        )
    return base_id


def _find_existing_table(client: httpx.Client, base_id: str, name: str) -> str | None:
    """base_id altinda verilen ad'a sahip tabloyu ara."""
    r = client.get(f"/api/v2/meta/bases/{base_id}/tables")
    if r.status_code >= 400:
        return None
    payload = r.json() or {}
    tables = payload.get("list") or payload.get("tables") or []
    for t in tables:
        if (t.get("table_name") or "").lower() == name.lower():
            return t.get("id")
        if (t.get("title") or "").lower() == name.lower():
            return t.get("id")
    return None


def create_settings_table(client: httpx.Client, base_id: str) -> tuple[str, str]:
    """Yarat (yoksa) veya bul. Returns (table_id, 'OK' | 'ALREADY EXISTS')."""
    existing = _find_existing_table(client, base_id, _TABLE_NAME)
    if existing:
        return existing, "ALREADY EXISTS"

    body = {
        "table_name": _TABLE_NAME,
        "title": _TABLE_NAME,
        # NocoDB v2 auto-adds an Id PK; passing an empty columns array works.
        "columns": [],
    }
    r = client.post(f"/api/v2/meta/bases/{base_id}/tables", json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"create table failed: {r.status_code} {r.text[:300]}"
        )
    data = r.json() or {}
    return data.get("id"), "OK"


def _get_table_meta(client: httpx.Client, table_id: str) -> dict[str, Any]:
    r = client.get(f"/api/v2/meta/tables/{table_id}")
    r.raise_for_status()
    return r.json()


def _find_column(meta: dict[str, Any], name: str) -> dict[str, Any] | None:
    for col in meta.get("columns") or []:
        if (col.get("column_name") or "").lower() == name.lower():
            return col
        if (col.get("title") or "").lower() == name.lower():
            return col
    return None


def ensure_column(
    client: httpx.Client,
    table_id: str,
    name: str,
    uidt: str,
    default: str | None = None,
) -> str:
    """Returns 'OK' or 'ALREADY EXISTS'."""
    meta = _get_table_meta(client, table_id)
    if _find_column(meta, name):
        return "ALREADY EXISTS"
    body: dict[str, Any] = {"column_name": name, "title": name, "uidt": uidt}
    if default is not None:
        body["cdf"] = default
    r = client.post(f"/api/v2/meta/tables/{table_id}/columns", json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"create column {name} failed: {r.status_code} {r.text[:300]}"
        )
    return "OK"


def ensure_initial_row(client: httpx.Client, table_id: str) -> str:
    """Tek satir patterni: tablo bossa Id=1 olarak insert et."""
    r = client.get(f"/api/v2/tables/{table_id}/records", params={"limit": 1})
    r.raise_for_status()
    rows = (r.json() or {}).get("list") or []
    if rows:
        return "ALREADY EXISTS"
    body = [{"outreach_paused": False}]
    r = client.post(f"/api/v2/tables/{table_id}/records", json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"insert initial row failed: {r.status_code} {r.text[:300]}"
        )
    return "OK"


def main() -> int:
    base_url = os.environ.get("NOCODB_BASE_URL")
    token = os.environ.get("NOCODB_API_TOKEN")
    settings_tbl = os.environ.get("NOCODB_SETTINGS_TABLE_ID")
    leads_tbl = os.environ.get("NOCODB_LEADS_TABLE_ID")

    if not (base_url and token):
        print(
            "FAIL: NOCODB_BASE_URL and NOCODB_API_TOKEN are required.",
            file=sys.stderr,
        )
        return 2
    if not settings_tbl and not leads_tbl:
        print(
            "FAIL: Either NOCODB_SETTINGS_TABLE_ID (existing table) or "
            "NOCODB_LEADS_TABLE_ID (so I can derive base_id and CREATE the "
            "table) must be set.",
            file=sys.stderr,
        )
        return 2

    print(f"Connecting to {base_url} ...")

    # Mode B: settings_tbl yoksa, leads_tbl'den base_id cikar ve tabloyu yarat
    if not settings_tbl:
        with _client(base_url, token) as c:
            try:
                base_id = _get_base_id_from_table(c, leads_tbl)
                print(f"  Derived base_id from Leadler: {base_id}")
                settings_tbl, status = create_settings_table(c, base_id)
                print(f"  [{status:>15}]  Create '{_TABLE_NAME}' table  (id={settings_tbl})")
                print()
                print(f"  >>> NocoDB Cloud Run env'ine EKLE:")
                print(f"  >>> NOCODB_SETTINGS_TABLE_ID={settings_tbl}")
                print()
            except Exception as exc:
                print(f"FAIL: could not create table: {exc}", file=sys.stderr)
                return 1
    with _client(base_url, token) as c:
        steps = [
            ("outreach_paused (Checkbox, default false)",
             lambda: ensure_column(c, settings_tbl, "outreach_paused", "Checkbox", default="false")),
            ("pause_reason (LongText)",
             lambda: ensure_column(c, settings_tbl, "pause_reason", "LongText")),
            ("paused_at (DateTime)",
             lambda: ensure_column(c, settings_tbl, "paused_at", "DateTime")),
            ("last_health_check (DateTime)",
             lambda: ensure_column(c, settings_tbl, "last_health_check", "DateTime")),
            ("last_decision_level (SingleLineText)",
             lambda: ensure_column(c, settings_tbl, "last_decision_level", "SingleLineText")),
            ("last_decision_reason (LongText)",
             lambda: ensure_column(c, settings_tbl, "last_decision_reason", "LongText")),
            ("last_metrics_json (LongText)",
             lambda: ensure_column(c, settings_tbl, "last_metrics_json", "LongText")),
            ("Initial row (Id=1)",
             lambda: ensure_initial_row(c, settings_tbl)),
        ]
        any_fail = False
        for label, fn in steps:
            try:
                status = fn()
                print(f"  [{status:>15}]  {label}")
            except Exception as exc:
                any_fail = True
                print(f"  [{'FAILED':>15}]  {label}  ->  {exc}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
