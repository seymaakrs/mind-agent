"""NocoDB schema migration: Leadler.asama'ya 'Itiraz' SingleSelect option.

Auto-reply intent=itiraz tespit ettiginde lead'i 'Itiraz' asama'sina
flag'lemek icin. Beyza/Sema NocoDB'de filter ile bu lead'leri ayri
gorebilir, raporlamada (count_leads asama='Itiraz') ayri metric olur.

Idempotent — zaten varsa atlar.

Run:
    export NOCODB_BASE_URL='http://34.26.138.196'
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'
    python scripts/migrate_itiraz_asama_option.py
"""
from __future__ import annotations

import os
import sys

from scripts.migrate_auto_reply_schema import _client, ensure_select_option


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
