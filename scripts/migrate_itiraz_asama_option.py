"""NocoDB schema migration: Leadler.asama'ya 'Itiraz' SingleSelect option.

Auto-reply intent=itiraz tespit ettiginde lead'i 'Itiraz' asama'sina
flag'lemek icin. Beyza/Sema NocoDB'de filter ile bu lead'leri ayri
gorebilir, raporlamada (count_leads asama='Itiraz') ayri metric olur.

Idempotent — zaten varsa atlar. Standalone (scripts/ paketi degil, direkt
``python scripts/migrate_itiraz_asama_option.py`` ile koşulur).

Run:
    export NOCODB_BASE_URL='http://34.26.138.196'
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'
    python scripts/migrate_itiraz_asama_option.py
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


def ensure_select_option(
    client: httpx.Client, table_id: str, column_name: str, option_label: str
) -> str:
    """Add a SingleSelect option to an existing column (idempotent)."""
    meta = _get_table_meta(client, table_id)
    col = _find_column(meta, column_name)
    if not col:
        raise RuntimeError(f"column {column_name} not found on table {table_id}")

    col_options = col.get("colOptions") or {}
    options = list(col_options.get("options") or [])
    existing_labels = {(o.get("title") or "").lower() for o in options}
    if option_label.lower() in existing_labels:
        return "ALREADY EXISTS"

    options.append({"title": option_label, "color": "#ffaaaa"})
    body = {"colOptions": {"options": options}}
    col_id = col.get("id")
    r = client.patch(f"/api/v2/meta/columns/{col_id}", json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"add option {option_label} to {column_name} failed: "
            f"{r.status_code} {r.text[:300]}"
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
        try:
            status = ensure_select_option(c, leads_tbl, "asama", "Itiraz")
            print(f"  [{status:>15}]  Leadler.asama option 'Itiraz'")
        except Exception as exc:
            print(f"  [{'FAILED':>15}]  {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
