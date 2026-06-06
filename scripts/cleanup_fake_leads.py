"""TEK SEFERLIK sahte/test lead temizligi (Adim 3).

KURAL: Bu hard-delete SADECE bu tek seferlik temizlik icindir. BUGUNDEN SONRA
hard-delete YASAK — sadece asama='Arsiv' flag kullanilir.

Silme kriterleri (herhangi biri tutuyorsa sahte sayilir):
  1. source_workflow_id == 'mind_agent_zernio_webhook'
  2. ad_soyad == 'Unknown'  (bosluk/buyuk-kucuk duyarsiz)
  3. notlar VEYA external_id/external_event_id icinde 'test' geciyor

Iliskili Etkilesimler satirlari da temizlenir (lead_id silinen lead Id'lerinde).

GUVENLIK: default DRY-RUN. Sayar, kolon adlarini + ornek satirlari gosterir,
Etkilesimler baglanti alanini otomatik tespit eder. HICBIR SEY SILMEZ.
Gercek silme icin --apply (Beyza onayindan SONRA).

Run (Cloud Shell):
    export NOCODB_BASE_URL='https://db.mindidai.com.tr'
    export NOCODB_API_TOKEN=...
    export NOCODB_LEADS_TABLE_ID='m5lcgc5ifeqh38h'
    export NOCODB_ETK_TABLE_ID='mx3kbw2vhwimxjf'      # Etkilesimler (opsiyonel)
    python scripts/cleanup_fake_leads.py              # DRY-RUN (say + raporla)
    python scripts/cleanup_fake_leads.py --apply      # GERCEK sil (onaydan sonra)
"""
from __future__ import annotations

import os
import sys
from typing import Any, Iterable

import httpx


_TIMEOUT = 30.0
_PAGE = 200

# Etkilesimler tablosunda lead'e baglanan alan icin aday isimler (otomatik tespit).
_ETK_LINK_CANDIDATES = ["lead_id", "leadId", "Leadler_id", "lead", "Lead", "Leadler"]


def _client(base_url: str, token: str) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"xc-token": token.strip(), "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )


def fetch_all_records(client: httpx.Client, table_id: str) -> list[dict[str, Any]]:
    """Tablodaki tum satirlari sayfalayarak ceker."""
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        r = client.get(
            f"/api/v2/tables/{table_id}/records",
            params={"limit": _PAGE, "offset": offset},
        )
        r.raise_for_status()
        payload = r.json() or {}
        rows = payload.get("list") or []
        out.extend(rows)
        page_info = payload.get("pageInfo") or {}
        if page_info.get("isLastPage") or not rows:
            break
        offset += _PAGE
        if offset > 100000:  # guvenlik freni
            break
    return out


def _has_test_token(row: dict[str, Any]) -> bool:
    """notlar veya external_id/external_event_id icinde 'test' geciyor mu."""
    for key in ("notlar", "external_id", "external_event_id"):
        val = row.get(key)
        if val and "test" in str(val).lower():
            return True
    return False


def is_fake_lead(row: dict[str, Any]) -> bool:
    """Silme kriterlerinden herhangi biri tutuyor mu (pure, test edilebilir)."""
    if row.get("source_workflow_id") == "mind_agent_zernio_webhook":
        return True
    name = (row.get("ad_soyad") or "").strip().lower()
    if name == "unknown":
        return True
    if _has_test_token(row):
        return True
    return False


def classify_reason(row: dict[str, Any]) -> str:
    """Hangi kriter(ler) tuttu — raporlama icin."""
    reasons = []
    if row.get("source_workflow_id") == "mind_agent_zernio_webhook":
        reasons.append("source_workflow_id=mind_agent_zernio_webhook")
    if (row.get("ad_soyad") or "").strip().lower() == "unknown":
        reasons.append("ad_soyad=Unknown")
    if _has_test_token(row):
        reasons.append("'test' notlar/external_id")
    return ", ".join(reasons)


def detect_etk_link_field(
    etk_rows: list[dict[str, Any]], lead_ids: set[Any]
) -> str | None:
    """Etkilesimler satirlarinda lead Id'lerine isaret eden alani otomatik bul."""
    if not etk_rows or not lead_ids:
        return None
    sample = etk_rows[: min(len(etk_rows), 500)]
    for field in _ETK_LINK_CANDIDATES:
        for row in sample:
            val = row.get(field)
            if isinstance(val, dict):  # NocoDB link object: {"Id": ...}
                val = val.get("Id") or val.get("id")
            if val in lead_ids:
                return field
    return None


def _row_id(row: dict[str, Any]) -> Any:
    return row.get("Id") or row.get("id")


def delete_records(
    client: httpx.Client, table_id: str, ids: Iterable[Any]
) -> int:
    """NocoDB v2 bulk delete. Returns silinen satir sayisi."""
    body = [{"Id": i} for i in ids if i is not None]
    if not body:
        return 0
    r = client.request(
        "DELETE", f"/api/v2/tables/{table_id}/records", json=body
    )
    if r.status_code >= 400:
        raise RuntimeError(f"delete failed: {r.status_code} {r.text[:300]}")
    return len(body)


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    dry_run = not apply

    base_url = os.environ.get("NOCODB_BASE_URL")
    token = os.environ.get("NOCODB_API_TOKEN")
    leads_tbl = os.environ.get("NOCODB_LEADS_TABLE_ID")
    etk_tbl = os.environ.get("NOCODB_ETK_TABLE_ID")

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
    token = token.strip()
    if "<" in token or ">" in token or not token.isascii():
        print(f"FAIL: NOCODB_API_TOKEN gecersiz gorunuyor: {token!r}", file=sys.stderr)
        return 2

    mode = "DRY-RUN (hicbir sey silinmez)" if dry_run else "APPLY (GERCEK SILME)"
    print(f"Connecting to {base_url} ...")
    print(f"Mode: {mode}\n")

    with _client(base_url, token) as c:
        leads = fetch_all_records(c, leads_tbl)
        print(f"Leadler toplam satir: {len(leads)}")
        if leads:
            print(f"Leadler kolonlari: {sorted(leads[0].keys())}\n")

        fakes = [r for r in leads if is_fake_lead(r)]
        fake_ids = {_row_id(r) for r in fakes if _row_id(r) is not None}

        print(f">>> SAHTE/TEST olarak isaretlenen lead sayisi: {len(fakes)}")
        for r in fakes[:25]:
            print(f"    Id={_row_id(r)!s:>6}  ad_soyad={str(r.get('ad_soyad'))[:20]:<20}  "
                  f"[{classify_reason(r)}]")
        if len(fakes) > 25:
            print(f"    ... +{len(fakes) - 25} satir daha")

        etk_to_delete: list[Any] = []
        link_field = None
        if etk_tbl:
            etk = fetch_all_records(c, etk_tbl)
            print(f"\nEtkilesimler toplam satir: {len(etk)}")
            if etk:
                print(f"Etkilesimler kolonlari: {sorted(etk[0].keys())}")
            link_field = detect_etk_link_field(etk, fake_ids)
            if link_field:
                for row in etk:
                    val = row.get(link_field)
                    if isinstance(val, dict):
                        val = val.get("Id") or val.get("id")
                    if val in fake_ids:
                        rid = _row_id(row)
                        if rid is not None:
                            etk_to_delete.append(rid)
                print(f">>> Iliskili Etkilesimler (alan='{link_field}'): "
                      f"{len(etk_to_delete)} satir")
            else:
                print(">>> Etkilesimler baglanti alani TESPIT EDILEMEDI — "
                      "Etkilesimler silinmeyecek. (Kolon adlarini kontrol et.)")
        else:
            print("\nNOCODB_ETK_TABLE_ID verilmedi — Etkilesimler atlandi.")

        print()
        if dry_run:
            print("=" * 56)
            print(f"DRY-RUN OZET: {len(fakes)} lead + {len(etk_to_delete)} etkilesim "
                  "SILINECEK (henuz silinmedi).")
            print("Gercek silme icin (Beyza onayindan SONRA):")
            print("    python scripts/cleanup_fake_leads.py --apply")
            print("=" * 56)
            return 0

        # APPLY — once Etkilesimler (FK guvenligi), sonra Leadler
        if etk_to_delete and etk_tbl:
            n = delete_records(c, etk_tbl, etk_to_delete)
            print(f"  [SILINDI]  Etkilesimler: {n} satir")
        n = delete_records(c, leads_tbl, fake_ids)
        print(f"  [SILINDI]  Leadler: {n} satir")
        print("\nBitti. BUGUNDEN SONRA hard-delete YOK — sadece asama='Arsiv'.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
