"""Firestore'daki brand_identity'i okur, pretty-print + prompt_summary.

Kullanim:
    python scripts/show_brand_identity.py <business_id>
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tools.brand import load_brand_identity  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanim: python scripts/show_brand_identity.py <business_id>")
        return 2

    business_id = sys.argv[1]
    bi = load_brand_identity(business_id)
    if bi is None:
        print(f"businesses/{business_id}/brand_identity/v1 yok.")
        return 1

    print("=" * 60)
    print(f"business_id: {bi.business_id}")
    print(f"source     : {bi.source}")
    print(f"schema     : v{bi.schema_version}")
    print(f"updated_at : {bi.updated_at.isoformat()}")
    print(f"filled?    : {bi.is_substantially_filled()}")
    print("=" * 60)
    print(bi.model_dump_json(indent=2, exclude_none=False))
    print("=" * 60)
    print("prompt_summary (agent prompt'una giren kompakt metin):")
    print(bi.prompt_summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
