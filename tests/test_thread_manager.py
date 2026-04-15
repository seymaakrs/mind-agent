"""Tests for src/infra/thread_manager.py"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.infra.thread_manager import ThreadManager, generate_thread_id, _MAX_HISTORY_ITEMS


# ---------------------------------------------------------------------------
# generate_thread_id
# ---------------------------------------------------------------------------


class TestGenerateThreadId:
    def test_returns_32_char_string(self):
        tid = generate_thread_id()
        assert len(tid) == 32

    def test_is_lowercase_hex(self):
        tid = generate_thread_id()
        assert all(c in "0123456789abcdef" for c in tid)

    def test_each_call_is_unique(self):
        ids = {generate_thread_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(*, exists: bool, data: dict | None = None) -> MagicMock:
    """Build a mock Firestore DocumentSnapshot."""
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def _make_firestore_chain(doc: MagicMock) -> MagicMock:
    """
    Build a mock that satisfies:
        db.collection(...).document(...).collection(...).document(...).get/set/...
    """
    mock_db = MagicMock()
    (
        mock_db
        .collection.return_value
        .document.return_value
        .collection.return_value
        .document.return_value
        .get.return_value
    ) = doc
    return mock_db


# ---------------------------------------------------------------------------
# ThreadManager.load
# ---------------------------------------------------------------------------


class TestThreadManagerLoad:
    """ThreadManager.load() davranislari."""

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_empty_list_when_thread_not_found(self, mock_get_client):
        mock_get_client.return_value = _make_firestore_chain(_make_doc(exists=False))

        result = ThreadManager().load("biz1", "thread1")
        assert result == []

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_messages_when_thread_exists(self, mock_get_client):
        messages = [{"role": "user", "content": "merhaba"}, {"role": "assistant", "content": "hey"}]
        mock_get_client.return_value = _make_firestore_chain(
            _make_doc(exists=True, data={"messages": messages})
        )

        result = ThreadManager().load("biz1", "thread1")
        assert result == messages

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_empty_list_on_firestore_exception(self, mock_get_client):
        mock_get_client.side_effect = RuntimeError("connection refused")

        result = ThreadManager().load("biz1", "thread1")
        assert result == []

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_empty_list_when_messages_not_a_list(self, mock_get_client):
        # Corrupt data — messages is a string instead of a list
        mock_get_client.return_value = _make_firestore_chain(
            _make_doc(exists=True, data={"messages": "corrupted"})
        )

        result = ThreadManager().load("biz1", "thread1")
        assert result == []

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_empty_list_when_messages_key_missing(self, mock_get_client):
        mock_get_client.return_value = _make_firestore_chain(
            _make_doc(exists=True, data={"created_at": "2026-01-01T00:00:00+00:00"})
        )

        result = ThreadManager().load("biz1", "thread1")
        assert result == []

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_returns_empty_list_when_to_dict_returns_none(self, mock_get_client):
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = None
        mock_get_client.return_value = _make_firestore_chain(doc)

        result = ThreadManager().load("biz1", "thread1")
        assert result == []


# ---------------------------------------------------------------------------
# ThreadManager.save
# ---------------------------------------------------------------------------


class TestThreadManagerSave:
    """ThreadManager.save() davranislari."""

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_does_nothing_when_messages_empty(self, mock_get_client):
        ThreadManager().save("biz1", "thread1", [])
        mock_get_client.assert_not_called()

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_writes_to_correct_firestore_path(self, mock_get_client):
        messages = [{"role": "user", "content": "test"}]

        # Existing doc that returns exists=False (first save)
        existing_doc = _make_doc(exists=False)
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        # Verify correct collection/document path was used
        mock_db.collection.assert_called_once_with("businesses")
        mock_db.collection.return_value.document.assert_called_once_with("biz1")
        mock_db.collection.return_value.document.return_value.collection.assert_called_once_with("threads")
        mock_db.collection.return_value.document.return_value.collection.return_value.document.assert_called_once_with("thread1")

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_trims_messages_over_max_limit(self, mock_get_client):
        # Build 150 messages
        messages = [{"role": "user", "content": str(i)} for i in range(150)]

        existing_doc = _make_doc(exists=False)
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        # set() should have been called with only the last _MAX_HISTORY_ITEMS
        set_call_args = doc_ref.set.call_args
        saved_messages = set_call_args[0][0]["messages"]
        assert len(saved_messages) == _MAX_HISTORY_ITEMS
        # Should be the LAST N items (oldest dropped)
        assert saved_messages[0]["content"] == str(150 - _MAX_HISTORY_ITEMS)

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_preserves_created_at_on_update(self, mock_get_client):
        original_created_at = "2026-01-01T00:00:00+00:00"
        messages = [{"role": "user", "content": "hi"}]

        existing_doc = _make_doc(
            exists=True,
            data={"created_at": original_created_at, "messages": []},
        )
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["created_at"] == original_created_at

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_sets_created_at_on_first_save(self, mock_get_client):
        messages = [{"role": "user", "content": "hi"}]

        existing_doc = _make_doc(exists=False)
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        saved_data = doc_ref.set.call_args[0][0]
        assert "created_at" in saved_data
        assert saved_data["created_at"] == saved_data["updated_at"]

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_does_not_raise_on_firestore_exception(self, mock_get_client):
        mock_get_client.side_effect = RuntimeError("network error")
        # Should not raise
        ThreadManager().save("biz1", "thread1", [{"role": "user", "content": "hi"}])

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_counts_user_turns_correctly(self, mock_get_client):
        messages = [
            {"role": "user", "content": "turn 1"},
            {"role": "assistant", "content": "reply 1"},
            {"role": "user", "content": "turn 2"},
            {"role": "assistant", "content": "reply 2"},
            {"role": "user", "content": "turn 3"},
        ]

        existing_doc = _make_doc(exists=False)
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        saved_data = doc_ref.set.call_args[0][0]
        assert saved_data["turn_count"] == 3

    @patch("src.infra.thread_manager.get_firestore_client")
    def test_uses_merge_false(self, mock_get_client):
        """Tum document'i atomik olarak degistirmek icin merge=False olmali."""
        messages = [{"role": "user", "content": "hi"}]

        existing_doc = _make_doc(exists=False)
        mock_db = MagicMock()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value = existing_doc
        mock_get_client.return_value = mock_db

        ThreadManager().save("biz1", "thread1", messages)

        set_kwargs = doc_ref.set.call_args[1]
        assert set_kwargs.get("merge") is False
