"""Tests for migrate_guardian_schema.py — Adim 8 system_settings migration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.migrate_guardian_schema import (
    _find_existing_table,
    _get_base_id_from_table,
    create_settings_table,
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


class TestGetBaseIdFromTable:
    def test_extracts_base_id(self):
        client = MagicMock()
        client.get.return_value = _ok({"id": "leads_tbl", "base_id": "base_abc"})
        assert _get_base_id_from_table(client, "leads_tbl") == "base_abc"

    def test_falls_back_to_alternate_keys(self):
        client = MagicMock()
        client.get.return_value = _ok({"id": "leads_tbl", "source_id": "base_xyz"})
        assert _get_base_id_from_table(client, "leads_tbl") == "base_xyz"

    def test_raises_when_no_base_id(self):
        client = MagicMock()
        client.get.return_value = _ok({"id": "leads_tbl"})
        with pytest.raises(RuntimeError, match="could not extract"):
            _get_base_id_from_table(client, "leads_tbl")


class TestFindExistingTable:
    def test_found_by_table_name(self):
        client = MagicMock()
        client.get.return_value = _ok({"list": [
            {"id": "t1", "table_name": "Leadler"},
            {"id": "t2", "table_name": "system_settings"},
        ]})
        assert _find_existing_table(client, "base_abc", "system_settings") == "t2"

    def test_not_found_returns_none(self):
        client = MagicMock()
        client.get.return_value = _ok({"list": []})
        assert _find_existing_table(client, "base_abc", "system_settings") is None


class TestCreateSettingsTable:
    def test_creates_when_missing(self):
        client = MagicMock()
        client.get.return_value = _ok({"list": []})
        client.post.return_value = _ok({"id": "new_tbl_id"})

        table_id, status = create_settings_table(client, "base_abc")
        assert status == "OK"
        assert table_id == "new_tbl_id"
        # Endpoint shape
        url = client.post.call_args.args[0]
        assert url == "/api/v2/meta/bases/base_abc/tables"
        body = client.post.call_args.kwargs["json"]
        assert body["table_name"] == "system_settings"

    def test_returns_existing_table_id(self):
        client = MagicMock()
        client.get.return_value = _ok({"list": [
            {"id": "already_there", "table_name": "system_settings"},
        ]})
        table_id, status = create_settings_table(client, "base_abc")
        assert status == "ALREADY EXISTS"
        assert table_id == "already_there"
        client.post.assert_not_called()

    def test_raises_on_create_failure(self):
        client = MagicMock()
        client.get.return_value = _ok({"list": []})
        client.post.return_value = _err(403, "forbidden")
        with pytest.raises(RuntimeError, match="403"):
            create_settings_table(client, "base_abc")
