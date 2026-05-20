"""NocoDB schema migration for Adim 6 (Auto-reply Agent).

What it adds (idempotent — safe to re-run):
1. Etkilesimler.auto_reply_processed  (Checkbox, default false)
2. Leadler.asama option 'Takipte'    (SingleSelect option)
3. Leadler.son_temas                  (DateTime — auto-reply runner yaziyor)
4. Etkilesimler.tur option 'Itiraz Yanit' (otonom itiraz yaniti logu)
5. Leadler.asama option 'Itiraz'     (itiraz yaniti sonrasi lead asama)

Run (Cloud Shell or SSH):
    export NOCODB_BASE_URL=https://nocodb.example.com
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID=...
    export NOCODB_MESSAGES_TABLE_ID=...
    python -m scripts.migrate_auto_reply_schema

Output: per-step "OK / ALREADY EXISTS / FAILED" summary, exit 0 on success.

Endpoints (NocoDB v2 meta API):
- GET    /api/v2/meta/tables/{tableId}        -> columns metadata
- POST   /api/v2/meta/tables/{tableId}/columns -> create column
- PATCH  /api/v2/meta/columns/{columnId}       -> mutate column (add option)
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


def ensure_checkbox_column(
    client: httpx.Client, table_id: str, name: str, default_false: bool = True
) -> str:
    """Returns 'OK', 'ALREADY EXISTS', or raises on hard failure."""
    meta = _get_table_meta(client, table_id)
    if _find_column(meta, name):
        return "ALREADY EXISTS"
    body = {
        "column_name": name,
        "title": name,
        "uidt": "Checkbox",
        "cdf": "false" if default_false else "true",
    }
    r = client.post(f"/api/v2/meta/tables/{table_id}/columns", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"create column {name} failed: {r.status_code} {r.text[:300]}")
    return "OK"


def ensure_datetime_column(client: httpx.Client, table_id: str, name: str) -> str:
    meta = _get_table_meta(client, table_id)
    if _find_column(meta, name):
        return "ALREADY EXISTS"
    body = {"column_name": name, "title": name, "uidt": "DateTime"}
    r = client.post(f"/api/v2/meta/tables/{table_id}/columns", json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"create column {name} failed: {r.status_code} {r.text[:300]}")
    return "OK"


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

    options.append({"title": option_label, "color": "#cfdffe"})
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
    msgs_tbl = os.environ.get("NOCODB_MESSAGES_TABLE_ID")

    missing = [
        k for k, v in {
            "NOCODB_BASE_URL": base_url,
            "NOCODB_API_TOKEN": token,
            "NOCODB_LEADS_TABLE_ID": leads_tbl,
            "NOCODB_MESSAGES_TABLE_ID": msgs_tbl,
        }.items() if not v
    ]
    if missing:
        print(f"FAIL: missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    print(f"Connecting to {base_url} ...")
    with _client(base_url, token) as c:
        steps = [
            (
                "Etkilesimler.auto_reply_processed (Checkbox, default false)",
                lambda: ensure_checkbox_column(c, msgs_tbl, "auto_reply_processed"),
            ),
            (
                "Leadler.asama option 'Takipte'",
                lambda: ensure_select_option(c, leads_tbl, "asama", "Takipte"),
            ),
            (
                "Leadler.son_temas (DateTime)",
                lambda: ensure_datetime_column(c, leads_tbl, "son_temas"),
            ),
            (
                "Etkilesimler.tur option 'Itiraz Yanit'",
                lambda: ensure_select_option(c, msgs_tbl, "tur", "Itiraz Yanit"),
            ),
            (
                "Leadler.asama option 'Itiraz'",
                lambda: ensure_select_option(c, leads_tbl, "asama", "Itiraz"),
            ),
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
