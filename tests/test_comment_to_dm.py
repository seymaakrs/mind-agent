"""Tests for src/agents/comment_to_dm/.

Coverage:
- classifier.CommentClassification Pydantic shape (no LLM call — empty text)
- policy.keyword_check (whitelist/blacklist gates)
- policy.already_dm_d_recently (24h idempotency window)
- responder.decide (decision matrix for all intents)
- runner.handle_comment E2E (config disabled / pricing → DM /
  compliment+opt-in → like+DM / complaint → notify_seyma / spam → tag)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.agents.comment_to_dm import policy as ctd_policy
from src.agents.comment_to_dm import responder as ctd_responder
from src.agents.comment_to_dm import runner as ctd_runner
from src.agents.comment_to_dm.classifier import CommentClassification


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class TestConfig:
    def test_default_disabled(self):
        cfg = ctd_policy.CommentToDMConfig.from_doc(None)
        assert cfg.enabled is False
        assert cfg.max_dms_per_day == 50

    def test_from_doc_parses_fields(self):
        cfg = ctd_policy.CommentToDMConfig.from_doc(
            {
                "enabled": True,
                "pricing_template": "ozel mesaj",
                "whitelist_keywords": ["fiyat", "ucret"],
                "blacklist_keywords": ["takipci"],
                "max_dms_per_day": 20,
                "thank_you_enabled": True,
            }
        )
        assert cfg.enabled is True
        assert cfg.pricing_template == "ozel mesaj"
        assert "fiyat" in cfg.whitelist_keywords
        assert cfg.thank_you_enabled is True


class TestKeywordCheck:
    def test_blacklist_blocks(self):
        cfg = ctd_policy.CommentToDMConfig(
            enabled=True, blacklist_keywords=("takipci",)
        )
        ok, why = ctd_policy.keyword_check("ucuz takipci satiyoruz", cfg)
        assert ok is False
        assert "blacklist" in why

    def test_whitelist_requires_match(self):
        cfg = ctd_policy.CommentToDMConfig(
            enabled=True, whitelist_keywords=("fiyat",)
        )
        ok, _ = ctd_policy.keyword_check("merhaba", cfg)
        assert ok is False
        ok, _ = ctd_policy.keyword_check("fiyat nedir", cfg)
        assert ok is True

    def test_no_lists_allows_all(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        ok, _ = ctd_policy.keyword_check("herhangi bir metin", cfg)
        assert ok is True


class TestAlreadyDmRecently:
    def test_none_returns_false(self):
        assert ctd_policy.already_dm_d_recently(None) is False

    def test_within_24h_true(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert ctd_policy.already_dm_d_recently(ts) is True

    def test_older_than_24h_false(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        assert ctd_policy.already_dm_d_recently(ts) is False


# ---------------------------------------------------------------------------
# Responder (decision matrix)
# ---------------------------------------------------------------------------


def _cls(intent: str, conf: float = 0.9) -> CommentClassification:
    return CommentClassification(intent=intent, confidence=conf, reasoning="t")


class TestDecide:
    def test_pricing_question_goes_to_dm(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("pricing_question", 0.9), cfg)
        assert d.action == "dm"
        assert "fiyat" in d.dm_text.lower() or "DM" in d.dm_text

    def test_availability_question_uses_avail_template(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("availability_question", 0.9), cfg)
        assert d.action == "dm"
        assert "musait" in d.dm_text.lower() or "tarih" in d.dm_text.lower()

    def test_compliment_optin_likes_and_dms(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True, thank_you_enabled=True)
        d = ctd_responder.decide(_cls("compliment", 0.95), cfg)
        assert d.action == "like_and_dm"

    def test_compliment_optout_ignored(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True, thank_you_enabled=False)
        d = ctd_responder.decide(_cls("compliment", 0.95), cfg)
        assert d.action == "ignore"

    def test_complaint_notifies_seyma(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("complaint", 0.9), cfg)
        assert d.action == "notify_seyma"

    def test_spam_tagged(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("spam", 0.9), cfg)
        assert d.action == "tag_spam"

    def test_low_confidence_ignored(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("pricing_question", 0.3), cfg)
        assert d.action == "ignore"

    def test_other_intent_ignored(self):
        cfg = ctd_policy.CommentToDMConfig(enabled=True)
        d = ctd_responder.decide(_cls("other", 0.9), cfg)
        assert d.action == "ignore"

    def test_uses_custom_pricing_template(self):
        cfg = ctd_policy.CommentToDMConfig(
            enabled=True, pricing_template="ozel teklif gonderdim"
        )
        d = ctd_responder.decide(_cls("pricing_question", 0.9), cfg)
        assert d.dm_text == "ozel teklif gonderdim"


# ---------------------------------------------------------------------------
# Runner E2E (with mocked classifier + zernio + firestore)
# ---------------------------------------------------------------------------


def _comment_event(text: str = "fiyat nedir?", intent: str | None = None) -> dict[str, Any]:
    return {
        "id": "evt-c-1",
        "event": "comment.received",
        "businessId": "biz-abc",
        "comment": {
            "id": "cmt-1",
            "postId": "post-1",
            "text": text,
            "platform": "instagram",
            "author": {"id": "user-9", "name": "Ali"},
        },
        "post": {"id": "post-1"},
    }


@pytest.fixture
def mocked_runner(monkeypatch):
    """Mock classifier, firestore, zernio. Returns helpers."""
    state: dict[str, Any] = {"classification": _cls("pricing_question", 0.9)}

    def _fake_classify_sync(text: str) -> CommentClassification:
        return state["classification"]

    monkeypatch.setattr(ctd_runner, "_classify_sync", _fake_classify_sync)

    # Firestore: enabled config, no prior idempotency record
    cfg_doc = MagicMock()
    cfg_doc.exists = True
    cfg_doc.to_dict.return_value = {"enabled": True, "thank_you_enabled": True}
    idemp_snap = MagicMock()
    idemp_snap.exists = False
    db = MagicMock()
    db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.side_effect = [
        cfg_doc,
        idemp_snap,
    ]
    monkeypatch.setattr(ctd_runner, "_get_firestore", lambda: db)

    # Zernio
    zclient = MagicMock()
    zclient.send_message.return_value = {"ok": True, "id": "msg-out-1"}
    zclient.like_comment.return_value = None
    zclient.tag_comment.return_value = None
    monkeypatch.setattr(ctd_runner, "_get_zernio", lambda: zclient)

    # NocoDB (for notify_seyma path)
    nocodb = MagicMock()
    nocodb.create_record.return_value = {"Id": 1}
    monkeypatch.setattr(ctd_runner, "_get_nocodb", lambda: nocodb)
    monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
    from src.app.config import get_settings
    get_settings.cache_clear()

    return {"state": state, "zclient": zclient, "db": db, "nocodb": nocodb}


class TestRunner:
    def test_disabled_config_skips(self, monkeypatch):
        cfg_doc = MagicMock()
        cfg_doc.exists = True
        cfg_doc.to_dict.return_value = {"enabled": False}
        db = MagicMock()
        db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = cfg_doc
        monkeypatch.setattr(ctd_runner, "_get_firestore", lambda: db)
        result = ctd_runner.handle_comment(_comment_event(), business_id="biz-abc")
        assert result["action"] == "ignore"
        assert "disabled" in result["reason"]

    def test_pricing_question_sends_dm(self, mocked_runner):
        mocked_runner["state"]["classification"] = _cls("pricing_question", 0.9)
        result = ctd_runner.handle_comment(_comment_event(), business_id="biz-abc")
        assert result["action"] == "dm"
        assert result["dm_sent"] is True
        mocked_runner["zclient"].send_message.assert_called_once()

    def test_complaint_notifies_seyma(self, mocked_runner):
        mocked_runner["state"]["classification"] = _cls("complaint", 0.9)
        result = ctd_runner.handle_comment(
            _comment_event("berbat hizmet"), business_id="biz-abc"
        )
        assert result["action"] == "notify_seyma"
        mocked_runner["zclient"].send_message.assert_not_called()
        assert result.get("seyma_notified") is True

    def test_spam_tags_comment(self, mocked_runner):
        mocked_runner["state"]["classification"] = _cls("spam", 0.95)
        result = ctd_runner.handle_comment(
            _comment_event("takipci satin al"), business_id="biz-abc"
        )
        assert result["action"] == "tag_spam"
        mocked_runner["zclient"].send_message.assert_not_called()

    def test_compliment_likes_and_dms(self, mocked_runner):
        mocked_runner["state"]["classification"] = _cls("compliment", 0.95)
        result = ctd_runner.handle_comment(
            _comment_event("harika!"), business_id="biz-abc"
        )
        assert result["action"] == "like_and_dm"
        assert result["dm_sent"] is True

    def test_idempotency_blocks_second_dm(self, monkeypatch):
        """Same author + same post within 24h → second call ignored."""
        cfg_doc = MagicMock()
        cfg_doc.exists = True
        cfg_doc.to_dict.return_value = {"enabled": True}
        recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        idemp_snap = MagicMock()
        idemp_snap.exists = True
        idemp_snap.to_dict.return_value = {"sent_at": recent}
        db = MagicMock()
        db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.side_effect = [
            cfg_doc, idemp_snap,
        ]
        monkeypatch.setattr(ctd_runner, "_get_firestore", lambda: db)
        monkeypatch.setattr(
            ctd_runner, "_classify_sync",
            lambda t: _cls("pricing_question", 0.9),
        )
        result = ctd_runner.handle_comment(_comment_event(), business_id="biz-abc")
        assert result["action"] == "ignore"
        assert "idempotency" in result["reason"]
