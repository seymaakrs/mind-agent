from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any


def generate_report_id(report_type: str) -> str:
    """Generate a unique report ID.

    Format: {type}-{YYYYMMDD}-{random6hex}
    Example: swot-20260123-abc123
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_hex = secrets.token_hex(3)
    return f"{report_type}-{date_str}-{random_hex}"


def flatten_block_for_firestore(block: dict[str, Any]) -> dict[str, Any]:
    """Flatten a block to avoid Firestore nested entity errors.

    Firestore has limits on nested arrays/maps. This function converts
    deeply nested structures to JSON strings.
    """
    flattened = {"type": block.get("type", "text")}

    for key, value in block.items():
        if key == "type":
            continue
        if key == "rows" and isinstance(value, list):
            flattened["rows_json"] = json.dumps(value, ensure_ascii=False)
        elif key == "items" and isinstance(value, list) and any(isinstance(item, (list, dict)) for item in value):
            flattened["items_json"] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[key] = value

    return flattened
