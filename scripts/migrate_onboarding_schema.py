"""NocoDB schema migration: Lead Onboarding state fields.

Adds (idempotent):
- Leadler.onboarding_step    Number  (default 0)
  0 = hic mail atilmamis (Sicak olunca welcome adayi)
  1 = welcome mail atildi
  2 = 24sa hatirlatma atildi
  3 = 72sa gorusme talebi atildi (final)
- Leadler.son_onboarding_step  DateTime  (24sa / 72sa hesaplamak icin)

n8n Lead Onboarding workflow her saatte tablodaki Sicak lead'lerin
state'ini bu iki field'a bakarak yonetir. Idempotent — zaten varsa
atlanir.

Standalone (paket import yok). Run:

    export NOCODB_BASE_URL='http://34.26.138.196'
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'
    python scripts/migrate_onboarding_schema.py
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
    """Idempotent column ekle. 'OK' veya 'ALREADY EXISTS' doner."""
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
    leads_tbl = os.environ.get("NOCODB_LEADS_TABLE_ID")

    missing = [
        k for k, v in {
            "NOCODB_BASE_URL": base_url,
            "NOCODB_API_TOKEN": token,
            "NOCODB_LEADS_TABLE_ID": leads_tbl,
        }.items() if not v
    ]
    if missing:
        print(f"FAIL: missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    print(f"Connecting to {base_url} ...")
    with _client(base_url, token) as c:
        steps = [
            ("onboarding_step (Number, default 0)",
             lambda: ensure_column(c, leads_tbl, "onboarding_step", "Number", default="0")),
            ("son_onboarding_step (DateTime)",
             lambda: ensure_column(c, leads_tbl, "son_onboarding_step", "DateTime")),
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
