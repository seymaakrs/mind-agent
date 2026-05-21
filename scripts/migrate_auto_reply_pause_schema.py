"""NocoDB schema migration for Faz 1 — auto_reply pause kontrolu.

Sales Director (yeni isim) auto_reply_pause/auto_reply_resume tool'larini
cagirinca system_settings (Id=1) satirina su 3 kolon yazilir:
- auto_reply_paused (Checkbox, default false)
- auto_reply_pause_reason (LongText)
- auto_reply_paused_at (DateTime)

Bu script idempotent: var olan kolonu atlar.

Pattern mirror: scripts/migrate_guardian_schema.py

Run (Cloud Shell):
    export NOCODB_BASE_URL=...
    export NOCODB_API_TOKEN=...
    export NOCODB_SETTINGS_TABLE_ID=...
    python scripts/migrate_auto_reply_pause_schema.py
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


def main() -> int:
    base_url = os.environ.get("NOCODB_BASE_URL")
    token = os.environ.get("NOCODB_API_TOKEN")
    settings_tbl = os.environ.get("NOCODB_SETTINGS_TABLE_ID")

    if not (base_url and token and settings_tbl):
        print(
            "FAIL: NOCODB_BASE_URL, NOCODB_API_TOKEN, NOCODB_SETTINGS_TABLE_ID required.",
            file=sys.stderr,
        )
        return 2

    print(f"Connecting to {base_url} ... table={settings_tbl}")
    any_fail = False
    with _client(base_url, token) as c:
        steps = [
            ("auto_reply_paused (Checkbox, default false)",
             lambda: ensure_column(c, settings_tbl, "auto_reply_paused", "Checkbox", default="false")),
            ("auto_reply_pause_reason (LongText)",
             lambda: ensure_column(c, settings_tbl, "auto_reply_pause_reason", "LongText")),
            ("auto_reply_paused_at (DateTime)",
             lambda: ensure_column(c, settings_tbl, "auto_reply_paused_at", "DateTime")),
        ]
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
