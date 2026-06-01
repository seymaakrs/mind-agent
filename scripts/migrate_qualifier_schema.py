"""NocoDB schema migration: Qualifier altyapisi (Leadler tablosu).

Bu migration "gercek lead toplama" oncesi semayi hazirlar. Hicbir veri SILMEZ,
sadece kolon/option EKLER (additive, geri uyumlu).

Leadler tablosuna eklenen kolonlar:
    - qualified              (Checkbox,        default false)
    - source                 (SingleSelect:    gmaps, ig, linkedin, meta_lead_ads,
                              mindid_form, itiraz, wa_inbound, manual)
    - qualification_reason   (LongText)
    - qualified_by           (SingleLineText)
    - qualified_at           (DateTime)
asama enum'una 'Arsiv' option eklenir.

Iki mod (GUVENLIK: default DRY-RUN):
    python scripts/migrate_qualifier_schema.py            # DRY-RUN (sadece raporlar)
    python scripts/migrate_qualifier_schema.py --apply    # GERCEK uygular

Idempotent — zaten var olan kolon/option atlanir, tekrar tekrar kosulabilir.

Run:
    export NOCODB_BASE_URL='http://34.26.138.196'
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'
    python scripts/migrate_qualifier_schema.py            # once dry-run
    python scripts/migrate_qualifier_schema.py --apply    # sonra gercek
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx


_TIMEOUT = 30.0

# source SingleSelect option'lari (lead'in nereden geldigi).
SOURCE_OPTIONS = [
    "gmaps",
    "ig",
    "linkedin",
    "meta_lead_ads",
    "mindid_form",
    "itiraz",
    "wa_inbound",
    "manual",
]

# asama enum'una eklenecek yeni option.
NEW_ASAMA_OPTION = "Arsiv"


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
    dry_run: bool = True,
) -> str:
    """Basit kolon ekle (Checkbox/LongText/DateTime/SingleLineText).

    Returns 'ALREADY EXISTS' | 'WOULD ADD' (dry-run) | 'OK' (applied).
    """
    meta = _get_table_meta(client, table_id)
    if _find_column(meta, name):
        return "ALREADY EXISTS"
    if dry_run:
        return "WOULD ADD"
    body: dict[str, Any] = {"column_name": name, "title": name, "uidt": uidt}
    if default is not None:
        body["cdf"] = default
    r = client.post(f"/api/v2/meta/tables/{table_id}/columns", json=body)
    if r.status_code >= 400:
        raise RuntimeError(
            f"create column {name} failed: {r.status_code} {r.text[:300]}"
        )
    return "OK"


def ensure_singleselect_column(
    client: httpx.Client,
    table_id: str,
    name: str,
    options: list[str],
    dry_run: bool = True,
) -> str:
    """SingleSelect kolonu yarat (yoksa) ya da eksik option'lari ekle.

    Returns:
        'ALREADY EXISTS'            -> kolon var, tum option'lar mevcut
        'WOULD ADD COLUMN'          -> dry-run, kolon hic yok
        'WOULD ADD OPTIONS: a, b'   -> dry-run, kolon var ama bazi option eksik
        'OK (CREATED)'              -> applied, kolon yaratildi
        'OK (+N OPTIONS)'           -> applied, N option eklendi
    """
    meta = _get_table_meta(client, table_id)
    col = _find_column(meta, name)

    if not col:
        if dry_run:
            return "WOULD ADD COLUMN"
        body = {
            "column_name": name,
            "title": name,
            "uidt": "SingleSelect",
            "colOptions": {
                "options": [{"title": o} for o in options]
            },
        }
        r = client.post(f"/api/v2/meta/tables/{table_id}/columns", json=body)
        if r.status_code >= 400:
            raise RuntimeError(
                f"create singleselect {name} failed: {r.status_code} {r.text[:300]}"
            )
        return "OK (CREATED)"

    # Kolon var — eksik option'lari bul
    col_options = col.get("colOptions") or {}
    existing = list(col_options.get("options") or [])
    existing_labels = {(o.get("title") or "").lower() for o in existing}
    missing = [o for o in options if o.lower() not in existing_labels]

    if not missing:
        return "ALREADY EXISTS"
    if dry_run:
        return "WOULD ADD OPTIONS: " + ", ".join(missing)

    new_opts = existing + [{"title": o} for o in missing]
    col_id = col.get("id")
    r = client.patch(
        f"/api/v2/meta/columns/{col_id}", json={"colOptions": {"options": new_opts}}
    )
    if r.status_code >= 400:
        raise RuntimeError(
            f"add options to {name} failed: {r.status_code} {r.text[:300]}"
        )
    return f"OK (+{len(missing)} OPTIONS)"


def ensure_select_option(
    client: httpx.Client,
    table_id: str,
    column_name: str,
    option_label: str,
    dry_run: bool = True,
) -> str:
    """Mevcut SingleSelect kolonuna tek bir option ekle (idempotent).

    Returns 'ALREADY EXISTS' | 'WOULD ADD' (dry-run) | 'OK' (applied).
    """
    meta = _get_table_meta(client, table_id)
    col = _find_column(meta, column_name)
    if not col:
        raise RuntimeError(f"column {column_name} not found on table {table_id}")

    col_options = col.get("colOptions") or {}
    options = list(col_options.get("options") or [])
    existing_labels = {(o.get("title") or "").lower() for o in options}
    if option_label.lower() in existing_labels:
        return "ALREADY EXISTS"
    if dry_run:
        return "WOULD ADD"

    options.append({"title": option_label, "color": "#cccccc"})
    col_id = col.get("id")
    r = client.patch(
        f"/api/v2/meta/columns/{col_id}", json={"colOptions": {"options": options}}
    )
    if r.status_code >= 400:
        raise RuntimeError(
            f"add option {option_label} to {column_name} failed: "
            f"{r.status_code} {r.text[:300]}"
        )
    return "OK"


def run_migration(
    client: httpx.Client, leads_tbl: str, dry_run: bool = True
) -> list[tuple[str, str]]:
    """Tum adimlari sirayla calistir. Returns [(label, status), ...]."""
    steps = [
        ("qualified (Checkbox, default false)",
         lambda: ensure_column(client, leads_tbl, "qualified", "Checkbox",
                               default="false", dry_run=dry_run)),
        ("source (SingleSelect: 8 option)",
         lambda: ensure_singleselect_column(client, leads_tbl, "source",
                                            SOURCE_OPTIONS, dry_run=dry_run)),
        ("qualification_reason (LongText)",
         lambda: ensure_column(client, leads_tbl, "qualification_reason",
                               "LongText", dry_run=dry_run)),
        ("qualified_by (SingleLineText)",
         lambda: ensure_column(client, leads_tbl, "qualified_by",
                               "SingleLineText", dry_run=dry_run)),
        ("qualified_at (DateTime)",
         lambda: ensure_column(client, leads_tbl, "qualified_at",
                               "DateTime", dry_run=dry_run)),
        (f"asama option '{NEW_ASAMA_OPTION}'",
         lambda: ensure_select_option(client, leads_tbl, "asama",
                                      NEW_ASAMA_OPTION, dry_run=dry_run)),
    ]
    results: list[tuple[str, str]] = []
    for label, fn in steps:
        try:
            status = fn()
        except Exception as exc:  # noqa: BLE001 — raporda goster, durma
            status = f"FAILED: {exc}"
        results.append((label, status))
    return results


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    dry_run = not apply

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

    mode = "DRY-RUN (hicbir sey degismez)" if dry_run else "APPLY (GERCEK)"
    print(f"Connecting to {base_url} ...")
    print(f"Mode: {mode}")
    print()

    with _client(base_url, token) as c:
        results = run_migration(c, leads_tbl, dry_run=dry_run)

    any_fail = False
    for label, status in results:
        if status.startswith("FAILED"):
            any_fail = True
        print(f"  [{status:>24}]  {label}")

    print()
    if dry_run:
        print(">>> Bu sadece ON IZLEME idi. Uygulamak icin: "
              "python scripts/migrate_qualifier_schema.py --apply")
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
