"""H-3 — Sales memory idempotency + key-collision contract.

``_save_sales_memory_impl`` writes to:
   ``businesses/{business_id}/sales_memory/{category}/notes/{key}``

Two production-critical properties must hold:

1. **Path determinism.** Same (business_id, category, key) maps to the same
   document, regardless of insertion order. A typo or whitespace drift
   that creates a sibling doc means the Manager remembers two different
   decisions for the same key — a silent split-brain.
2. **Idempotent upsert.** Calling save twice with the same key MUST overwrite
   (merge=True). The Firestore document client is the source of truth for
   this — the test exercises the impl with an in-memory fake and asserts
   the second call lands on the same doc id.

If either property regresses, the Manager's memory turns into a duplicate
graveyard. These tests fence both at the unit boundary.
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("agents", reason="OpenAI Agents SDK required (production deps)")

from src.tools.sales import memory_tools as mt


class _FakeDocClient:
    """In-memory stand-in for Firestore subcollection access."""

    def __init__(self, store: dict[str, dict[str, Any]]):
        self._store = store
        self.set_calls: list[tuple[str, dict, bool]] = []

    def get_document(self, key: str) -> dict | None:
        return self._store.get(key)

    def set_document(self, key: str, data: dict, merge: bool = False) -> None:
        self.set_calls.append((key, data, merge))
        existing = self._store.get(key, {}) if merge else {}
        merged = {**existing, **data}
        self._store[key] = merged


@pytest.fixture
def fake_firestore(monkeypatch):
    """Patch get_document_client so all calls hit a single fake store."""
    store: dict[str, dict[str, dict[str, Any]]] = {}
    clients: dict[str, _FakeDocClient] = {}

    def _get(path: str) -> _FakeDocClient:
        store.setdefault(path, {})
        if path not in clients:
            clients[path] = _FakeDocClient(store[path])
        return clients[path]

    monkeypatch.setattr(mt, "get_document_client", _get)
    return store, clients


def test_notes_path_deterministic_across_calls():
    p1 = mt._notes_path("biz_abc", "decisions")
    p2 = mt._notes_path("biz_abc", "decisions")
    assert p1 == p2 == "businesses/biz_abc/sales_memory/decisions/notes"


@pytest.mark.parametrize(
    "bid_a,bid_b,cat_a,cat_b,same",
    [
        ("biz_abc", "biz_abc", "decisions", "decisions", True),
        ("biz_abc", "biz_xyz", "decisions", "decisions", False),
        ("biz_abc", "biz_abc", "decisions", "learnings", False),
    ],
)
def test_notes_path_distinguishes_tenants_and_categories(bid_a, bid_b, cat_a, cat_b, same):
    p1 = mt._notes_path(bid_a, cat_a)
    p2 = mt._notes_path(bid_b, cat_b)
    assert (p1 == p2) is same


@pytest.mark.asyncio
async def test_save_same_key_twice_overwrites_with_merge(fake_firestore):
    store, clients = fake_firestore
    r1 = await mt._save_sales_memory_impl(
        business_id="biz_abc",
        category="decisions",
        key="slowdays_pause",
        value="Pause edildi sebep: yanit oranı düşük",
        reason="Yanit oranı %5'in altına düştü, Bekçi RED verdi",
    )
    assert r1["success"] is True, r1

    r2 = await mt._save_sales_memory_impl(
        business_id="biz_abc",
        category="decisions",
        key="slowdays_pause",
        value="Resume edildi: kalibrasyon sonrası dene",
        reason="Manuel inceleme tamam, yeniden başlatılıyor",
    )
    assert r2["success"] is True, r2

    # Single document under the deterministic path
    path = "businesses/biz_abc/sales_memory/decisions/notes"
    assert path in store
    assert list(store[path].keys()) == ["slowdays_pause"], (
        f"Expected exactly one doc; got: {list(store[path].keys())}"
    )

    # The second write overwrites the value but preserves created_at
    doc = store[path]["slowdays_pause"]
    assert doc["value"].startswith("Resume edildi"), doc["value"]
    assert "created_at" in doc and "updated_at" in doc

    # Both calls used merge=True
    fake = clients[path]
    assert len(fake.set_calls) == 2
    assert all(call[2] is True for call in fake.set_calls), (
        "Both writes must use merge=True (idempotent upsert contract)."
    )


@pytest.mark.asyncio
async def test_save_rejects_unknown_category(fake_firestore):
    r = await mt._save_sales_memory_impl(
        business_id="biz_abc",
        category="not_a_real_category",
        key="x",
        value="hello world",
        reason="checking validation",
    )
    assert r["success"] is False
    assert "category" in r["error"].lower()


@pytest.mark.asyncio
async def test_save_rejects_short_inputs(fake_firestore):
    common = dict(
        business_id="biz_abc",
        category="decisions",
        value="hello world",
        reason="audit-trail reason",
    )
    r = await mt._save_sales_memory_impl(key="x", **common)
    assert r["success"] is False and "key" in r["error"]

    r = await mt._save_sales_memory_impl(
        business_id="biz_abc",
        category="decisions",
        key="ok_key",
        value="hi",
        reason="audit-trail reason",
    )
    assert r["success"] is False and "value" in r["error"]
