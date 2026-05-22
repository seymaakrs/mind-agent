"""Tests for src/app/zernio_webhook_dispatcher.py — Part 1 webhook expansion.

Covers:
- post.published → Firestore ``status=published`` write
- post.failed → errors/ doc + Bekci alert webhook POST
- account.disconnected → businesses.{id}.connections.{platform}=disconnected
- comment.received → delegated to comment_to_dm.runner
- message.sent → Etkilesimler upsert idempotent on external_message_id
- post.boost.completed → ads_history doc
- Unknown event → 200 ack with action=skipped
- Replay-attack guard (same event id twice → second is skipped)
- Per-event feature flag (ZERNIO_EVENT_*_ENABLED=false)
- Legacy ``message.received`` flow untouched (delegates to legacy handle)
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.app import zernio_webhook_dispatcher as zwd  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state():
    zwd._reset_replay_cache()
    yield
    zwd._reset_replay_cache()


def _post_published(eid: str = "evt-pp-1") -> dict[str, Any]:
    return {
        "id": eid,
        "event": "post.published",
        "businessId": "biz-abc",
        "post": {
            "id": "post-123",
            "publishedAt": "2026-05-22T12:00:00Z",
            "permalink": "https://instagram.com/p/xyz",
        },
    }


class TestPostPublished:
    def test_writes_firestore_published(self, monkeypatch):
        db = MagicMock()
        ref = MagicMock()
        (
            db.collection.return_value.document.return_value.collection.return_value.document.return_value
        ) = ref
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        result = zwd.dispatch(_post_published())
        assert result["success"] is True
        assert result["decision"]["action"] == "post_marked_published"
        ref.set.assert_called_once()
        args, kwargs = ref.set.call_args
        assert args[0]["status"] == "published"
        assert kwargs.get("merge") is True

    def test_missing_business_id_skips(self, monkeypatch):
        monkeypatch.setattr(zwd, "_get_firestore", lambda: MagicMock())
        payload = {
            "id": "evt-pp-2",
            "event": "post.published",
            "post": {"id": "p-1"},
        }
        result = zwd.dispatch(payload)
        assert result["decision"]["action"] == "skipped"


class TestPostFailed:
    def test_logs_to_errors_and_alerts(self, monkeypatch):
        db = MagicMock()
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        monkeypatch.setenv("GUARDIAN_ALERT_WEBHOOK_URL", "http://alert.example")

        posted: list[dict[str, Any]] = []

        class _C:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, url, json=None):
                posted.append({"url": url, "json": json})

        import httpx

        monkeypatch.setattr(httpx, "Client", lambda **kw: _C())

        payload = {
            "id": "evt-pf-1",
            "event": "post.failed",
            "businessId": "biz-abc",
            "post": {"id": "p-9", "errorMessage": "rate limited"},
        }
        result = zwd.dispatch(payload)
        assert result["decision"]["action"] == "post_failed_logged"
        db.collection.assert_called_with("errors")
        assert posted and posted[0]["url"] == "http://alert.example"
        assert posted[0]["json"]["kind"] == "post_failed"


class TestAccountDisconnected:
    def test_flips_connection_status(self, monkeypatch):
        db = MagicMock()
        biz_ref = MagicMock()
        db.collection.return_value.document.return_value = biz_ref
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        monkeypatch.delenv("NOCODB_MESSAGES_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()

        payload = {
            "id": "evt-ad-1",
            "event": "account.disconnected",
            "businessId": "biz-abc",
            "account": {"id": "acc-1", "platform": "instagram"},
            "reason": "token_expired",
        }
        result = zwd.dispatch(payload)
        assert result["decision"]["action"] == "account_disconnected"
        biz_ref.set.assert_called_once()
        args, kwargs = biz_ref.set.call_args
        assert args[0]["connections"]["instagram"]["status"] == "disconnected"
        assert args[0]["connections"]["instagram"]["reason"] == "token_expired"


class TestMessageSent:
    def test_upserts_etkilesimler(self, monkeypatch):
        nocodb = MagicMock()
        nocodb.upsert_record.return_value = {"created": True, "record": {"Id": 555}}
        monkeypatch.setattr(zwd, "_get_nocodb", lambda: nocodb)
        monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
        from src.app.config import get_settings
        get_settings.cache_clear()

        payload = {
            "id": "evt-ms-1",
            "event": "message.sent",
            "message": {
                "platformMessageId": "wamid.out-1",
                "platform": "whatsapp",
                "text": "Selam!",
                "sentAt": "2026-05-22T12:00:00Z",
            },
        }
        result = zwd.dispatch(payload)
        assert result["decision"]["action"] == "message_sent_logged"
        args = nocodb.upsert_record.call_args.args
        assert args[1] == "external_message_id"


class TestBoostCompleted:
    def test_writes_ads_history(self, monkeypatch):
        db = MagicMock()
        ref = MagicMock()
        (
            db.collection.return_value.document.return_value.collection.return_value.document.return_value
        ) = ref
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        payload = {
            "id": "evt-bc-1",
            "event": "post.boost.completed",
            "businessId": "biz-abc",
            "campaign": {"id": "camp-1", "spend": 12.5, "ctr": 0.03},
        }
        result = zwd.dispatch(payload)
        assert result["decision"]["action"] == "boost_logged"
        args, _ = ref.set.call_args
        assert args[0]["campaign_id"] == "camp-1"
        assert args[0]["spend"] == 12.5


class TestUnknownEvent:
    def test_unknown_event_acks_200(self):
        result = zwd.dispatch({"id": "evt-u-1", "event": "weird.thing"})
        assert result["success"] is True
        assert result["decision"]["action"] == "skipped"
        assert "unknown" in result["decision"]["reason"]


class TestReplayAttack:
    def test_duplicate_event_id_skipped(self, monkeypatch):
        db = MagicMock()
        ref = MagicMock()
        (
            db.collection.return_value.document.return_value.collection.return_value.document.return_value
        ) = ref
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        payload = _post_published(eid="evt-replay-1")
        r1 = zwd.dispatch(payload)
        r2 = zwd.dispatch(payload)
        assert r1["decision"]["action"] == "post_marked_published"
        assert r2.get("replay") is True
        # only one firestore set
        assert ref.set.call_count == 1


class TestFeatureFlag:
    def test_disabled_event_short_circuits(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_EVENT_COMMENT_RECEIVED_ENABLED", "false")
        result = zwd.dispatch({"id": "evt-flag-1", "event": "comment.received"})
        assert result["success"] is True
        assert result.get("disabled") is True
        assert result["decision"]["action"] == "skipped"

    def test_enabled_default_true(self, monkeypatch):
        monkeypatch.delenv("ZERNIO_EVENT_POST_PUBLISHED_ENABLED", raising=False)
        db = MagicMock()
        ref = MagicMock()
        (
            db.collection.return_value.document.return_value.collection.return_value.document.return_value
        ) = ref
        monkeypatch.setattr(zwd, "_get_firestore", lambda: db)
        result = zwd.dispatch(_post_published(eid="evt-flag-2"))
        assert result.get("disabled") is None
        assert result["decision"]["action"] == "post_marked_published"


class TestLegacyMessageReceivedThroughDispatcher:
    """Even via dispatcher, message.received delegates to legacy handle()."""

    def test_delegates_to_legacy(self, monkeypatch):
        from src.app import zernio_webhook as zw

        called = {}

        def _fake_handle(payload):
            called["yes"] = True
            return {"success": True, "lead_id": 1, "created": True, "external_id": "x"}

        monkeypatch.setattr(zw, "handle", _fake_handle)
        result = zwd.dispatch({"id": "evt-mr-1", "event": "message.received"})
        assert called.get("yes") is True
        assert result["decision"]["action"] == "legacy_message_received"
