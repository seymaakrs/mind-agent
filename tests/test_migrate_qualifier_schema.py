"""Tests for migrate_qualifier_schema.py — Qualifier altyapisi migration.

Idempotency + dry-run davranisini dogrular. Network yok: httpx client
MagicMock ile taklit edilir.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.migrate_qualifier_schema import (
    SOURCE_OPTIONS,
    ensure_column,
    ensure_select_option,
    ensure_singleselect_column,
    run_migration,
)


def _ok(json_data):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_data
    r.raise_for_status.return_value = None
    return r


def _err(status, text="boom"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    return r


def _meta(columns):
    """Tablo meta'si — columns: list of dicts."""
    return _ok({"columns": columns})


class TestEnsureColumn:
    def test_already_exists_skips(self):
        client = MagicMock()
        client.get.return_value = _meta([{"column_name": "qualified"}])
        assert ensure_column(client, "t", "qualified", "Checkbox") == "ALREADY EXISTS"
        client.post.assert_not_called()

    def test_dry_run_does_not_write(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        assert ensure_column(client, "t", "qualified", "Checkbox",
                             dry_run=True) == "WOULD ADD"
        client.post.assert_not_called()

    def test_apply_creates_column_with_default(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        client.post.return_value = _ok({"id": "c1"})
        status = ensure_column(client, "t", "qualified", "Checkbox",
                               default="false", dry_run=False)
        assert status == "OK"
        body = client.post.call_args.kwargs["json"]
        assert body["uidt"] == "Checkbox"
        assert body["cdf"] == "false"

    def test_apply_raises_on_failure(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        client.post.return_value = _err(403, "forbidden")
        with pytest.raises(RuntimeError, match="403"):
            ensure_column(client, "t", "qualified", "Checkbox", dry_run=False)


class TestEnsureSingleSelectColumn:
    def test_dry_run_when_missing(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        assert ensure_singleselect_column(client, "t", "source", SOURCE_OPTIONS,
                                          dry_run=True) == "WOULD ADD COLUMN"
        client.post.assert_not_called()

    def test_apply_creates_with_all_options(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        client.post.return_value = _ok({"id": "c1"})
        status = ensure_singleselect_column(client, "t", "source", SOURCE_OPTIONS,
                                            dry_run=False)
        assert status == "OK (CREATED)"
        body = client.post.call_args.kwargs["json"]
        assert body["uidt"] == "SingleSelect"
        titles = [o["title"] for o in body["colOptions"]["options"]]
        assert titles == SOURCE_OPTIONS

    def test_already_exists_when_all_options_present(self):
        existing = [{"title": o} for o in SOURCE_OPTIONS]
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "source", "id": "c1",
             "colOptions": {"options": existing}},
        ])
        assert ensure_singleselect_column(client, "t", "source", SOURCE_OPTIONS,
                                          dry_run=False) == "ALREADY EXISTS"
        client.patch.assert_not_called()

    def test_dry_run_reports_missing_options(self):
        existing = [{"title": "gmaps"}, {"title": "ig"}]
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "source", "id": "c1",
             "colOptions": {"options": existing}},
        ])
        status = ensure_singleselect_column(client, "t", "source", SOURCE_OPTIONS,
                                            dry_run=True)
        assert status.startswith("WOULD ADD OPTIONS:")
        assert "linkedin" in status
        assert "gmaps" not in status  # zaten var
        client.patch.assert_not_called()

    def test_apply_adds_only_missing_options(self):
        existing = [{"title": "gmaps"}, {"title": "ig"}]
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "source", "id": "c1",
             "colOptions": {"options": existing}},
        ])
        client.patch.return_value = _ok({})
        status = ensure_singleselect_column(client, "t", "source", SOURCE_OPTIONS,
                                            dry_run=False)
        assert status == f"OK (+{len(SOURCE_OPTIONS) - 2} OPTIONS)"
        sent = client.patch.call_args.kwargs["json"]["colOptions"]["options"]
        # mevcutlar korunur + eksikler eklenir
        sent_titles = [o["title"] for o in sent]
        assert "gmaps" in sent_titles and "linkedin" in sent_titles
        assert len(sent_titles) == len(SOURCE_OPTIONS)


class TestEnsureSelectOption:
    def test_already_exists(self):
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "asama", "id": "c1",
             "colOptions": {"options": [{"title": "Arsiv"}]}},
        ])
        assert ensure_select_option(client, "t", "asama", "Arsiv") == "ALREADY EXISTS"
        client.patch.assert_not_called()

    def test_dry_run(self):
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "asama", "id": "c1",
             "colOptions": {"options": [{"title": "Yeni"}]}},
        ])
        assert ensure_select_option(client, "t", "asama", "Arsiv",
                                    dry_run=True) == "WOULD ADD"
        client.patch.assert_not_called()

    def test_apply_appends_option(self):
        client = MagicMock()
        client.get.return_value = _meta([
            {"column_name": "asama", "id": "c1",
             "colOptions": {"options": [{"title": "Yeni"}]}},
        ])
        client.patch.return_value = _ok({})
        assert ensure_select_option(client, "t", "asama", "Arsiv",
                                    dry_run=False) == "OK"
        sent = client.patch.call_args.kwargs["json"]["colOptions"]["options"]
        assert {"title": "Yeni"} in sent
        assert any(o["title"] == "Arsiv" for o in sent)

    def test_missing_column_raises(self):
        client = MagicMock()
        client.get.return_value = _meta([])
        with pytest.raises(RuntimeError, match="not found"):
            ensure_select_option(client, "t", "asama", "Arsiv")


class TestRunMigration:
    def test_dry_run_full_fresh_table(self):
        """Hicbir kolon yok — hepsi WOULD ADD, hicbir yazma olmaz."""
        client = MagicMock()
        # asama kolonu var (Arsiv option eklenebilsin), digerleri yok
        client.get.return_value = _meta([
            {"column_name": "asama", "id": "asama_col",
             "colOptions": {"options": [{"title": "Yeni"}]}},
        ])
        results = run_migration(client, "t", dry_run=True)
        labels = [s for _, s in results]
        assert all(not s.startswith("FAILED") for s in labels)
        assert "WOULD ADD" in labels  # qualified
        assert "WOULD ADD COLUMN" in labels  # source
        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_idempotent_second_run_all_exists(self):
        """Her sey zaten var — hepsi ALREADY EXISTS."""
        all_cols = [
            {"column_name": "qualified"},
            {"column_name": "source", "id": "s",
             "colOptions": {"options": [{"title": o} for o in SOURCE_OPTIONS]}},
            {"column_name": "qualification_reason"},
            {"column_name": "qualified_by"},
            {"column_name": "qualified_at"},
            {"column_name": "asama", "id": "a",
             "colOptions": {"options": [{"title": "Arsiv"}]}},
        ]
        client = MagicMock()
        client.get.return_value = _meta(all_cols)
        results = run_migration(client, "t", dry_run=False)
        assert all(s == "ALREADY EXISTS" for _, s in results)
        client.post.assert_not_called()
        client.patch.assert_not_called()
