"""NocoDB schema migration for Adim 8 (Guardian / Bekci Robot).

Adds (idempotent):
1. ``system_settings`` table — Cloud Shell'den koşmadan ÖNCE Beyza UI'da
   "system_settings" adinda BOŞ bir tablo yaratacak ve TABLE ID'sini
   ``NOCODB_SETTINGS_TABLE_ID`` env'ine verecek (NocoDB v2 meta API tablo
   yaratma için baseId gerek, kullanıcının vermediği bir env — UI 1 dakika).
2. Yukaridaki tabloya su Checkbox/Text/DateTime kolonlari:
   - outreach_paused      Checkbox (default false) — Outreach Robotu bunu
                          her tick'te okur; True ise mesaj atmaz.
   - pause_reason         LongText — Bekci'nin yazdigi sebep
   - paused_at            DateTime — pause zamani
   - last_health_check    DateTime — Bekci'nin son tick'i
   - last_decision_level  Text — GREEN/YELLOW/RED/INSUFFICIENT
   - last_decision_reason LongText
   - last_metrics_json    LongText — son hesaplanan metric'lerin JSON'i
3. Tablonun TEK satirini olusturur (Id=1 by convention) eger bossa.

Run:
    export NOCODB_BASE_URL=...
    export NOCODB_API_TOKEN=...
    export NOCODB_SETTINGS_TABLE_ID=...    # UI'dan kopyaladığın tablo ID
    python scripts/migrate_guardian_schema.py
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx


_TIMEOUT = 30.0


def _client(base_url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"xc-token": token, "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )


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

    missing = [
        k for k, v in {
            "NOCODB_BASE_URL": base_url,
            "NOCODB_API_TOKEN": token,
            "NOCODB_SETTINGS_TABLE_ID": settings_tbl,
        }.items() if not v
    ]
    if missing:
        print(f"FAIL: missing env vars: {', '.join(missing)}", file=sys.stderr)
        print(
            "Hint: NocoDB UI'da 'system_settings' adında BOŞ bir tablo yarat, "
            "table id'sini NOCODB_SETTINGS_TABLE_ID env'ine ver.",
            file=sys.stderr,
        )
        return 2

    print(f"Connecting to {base_url} ...")
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
