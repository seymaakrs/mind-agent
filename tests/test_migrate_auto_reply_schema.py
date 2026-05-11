"""Tests for scripts/migrate_auto_reply_schema.py (idempotent + happy path)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.migrate_auto_reply_schema import (
    _find_column,
    ensure_checkbox_column,
    ensure_datetime_column,
    ensure_select_option,
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


class TestFindColumn:
    def test_matches_by_column_name(self):
        meta = {"columns": [{"column_name": "auto_reply_processed", "id": "c1"}]}
        assert _find_column(meta, "auto_reply_processed")["id"] == "c1"

    def test_matches_by_title_case_insensitive(self):
        meta = {"columns": [{"title": "Asama", "id": "c2"}]}
        assert _find_column(meta, "asama")["id"] == "c2"

    def test_returns_none_when_missing(self):
        assert _find_column({"columns": []}, "x") is None


class TestEnsureCheckboxColumn:
    def test_creates_when_missing(self):
        client = MagicMock()
        client.get.return_value = _ok({"columns": []})
        client.post.return_value = _ok({"id": "new"})

        assert ensure_checkbox_column(client, "tbl", "auto_reply_processed") == "OK"
        body = client.post.call_args.kwargs["json"]
        assert body["uidt"] == "Checkbox"
        assert body["cdf"] == "false"
        assert body["column_name"] == "auto_reply_processed"

    def test_skips_when_already_exists(self):
        client = MagicMock()
        client.get.return_value = _ok(
            {"columns": [{"column_name": "auto_reply_processed", "id": "c1"}]}
        )
        assert ensure_checkbox_column(client, "tbl", "auto_reply_processed") == "ALREADY EXISTS"
        client.post.assert_not_called()

    def test_raises_on_api_error(self):
        client = MagicMock()
        client.get.return_value = _ok({"columns": []})
        client.post.return_value = _err(403, "forbidden")
        with pytest.raises(RuntimeError, match="403"):
            ensure_checkbox_column(client, "tbl", "x")


class TestEnsureSelectOption:
    def test_adds_option_to_existing_column(self):
        client = MagicMock()
        client.get.return_value = _ok({
            "columns": [{
                "column_name": "asama",
                "id": "col-asama",
                "colOptions": {"options": [{"title": "Yeni"}, {"title": "Sicak"}]},
            }]
        })
        client.patch.return_value = _ok({})

        assert ensure_select_option(client, "tbl", "asama", "Takipte") == "OK"
        body = client.patch.call_args.kwargs["json"]
        labels = {o["title"] for o in body["colOptions"]["options"]}
        assert labels == {"Yeni", "Sicak", "Takipte"}

    def test_skips_when_option_present(self):
        client = MagicMock()
        client.get.return_value = _ok({
            "columns": [{
                "column_name": "asama",
                "id": "col-asama",
                "colOptions": {"options": [{"title": "Takipte"}]},
            }]
        })
        assert ensure_select_option(client, "tbl", "asama", "takipte") == "ALREADY EXISTS"
        client.patch.assert_not_called()

    def test_raises_when_column_missing(self):
        client = MagicMock()
        client.get.return_value = _ok({"columns": []})
        with pytest.raises(RuntimeError, match="not found"):
            ensure_select_option(client, "tbl", "asama", "Takipte")


class TestEnsureDateTimeColumn:
    def test_creates_when_missing(self):
        client = MagicMock()
        client.get.return_value = _ok({"columns": []})
        client.post.return_value = _ok({})
        assert ensure_datetime_column(client, "tbl", "son_temas") == "OK"
        body = client.post.call_args.kwargs["json"]
        assert body["uidt"] == "DateTime"
