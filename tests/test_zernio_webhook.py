"""Tests for src/app/zernio_webhook.py and the /zernio/webhook FastAPI route.

Coverage:
- Signature verification: soft mode (no secret), strict mode (valid/invalid/missing).
- Payload mapping: external_id (BSUID > phone > sender.id), kaynak by platform,
  asama by direction, score formula matching Adim 3 jsCode.
- Handler: target vs non-target event (skipped), idempotency via external_id,
  best-effort message log (lead survives if Etkilesimler write fails).
- Route: 401 on bad signature, 400 on invalid JSON, 200 on happy path.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.app import zernio_webhook as zw  # noqa: E402


# ---------------------------------------------------------------------------
# Sample payload
# ---------------------------------------------------------------------------


def _msg_received(
    *,
    text: str = "Merhaba bilgi alabilir miyim?",
    platform: str = "whatsapp",
    direction: str = "incoming",
    bsuid: str | None = "bsuid-123",
    phone: str | None = "+905551112233",
    sender_id: str = "905551112233",
    name: str = "Ide Beach Home",
    platform_message_id: str | None = "wamid.test123",
) -> dict[str, Any]:
    sender: dict[str, Any] = {"id": sender_id, "name": name}
    if phone is not None:
        sender["phoneNumber"] = phone
    if bsuid is not None:
        sender["businessScopedUserId"] = bsuid
    msg: dict[str, Any] = {
        "id": "msg-1",
        "conversationId": "conv-1",
        "platform": platform,
        "direction": direction,
        "text": text,
        "sender": sender,
        "sentAt": "2026-05-09T16:00:00Z",
        "isRead": False,
    }
    if platform_message_id is not None:
        msg["platformMessageId"] = platform_message_id
    return {
        "id": "evt-1",
        "event": "message.received",
        "message": msg,
        "conversation": {"id": "conv-1", "participantName": name, "status": "active"},
        "account": {"id": "wa-acc", "platform": platform, "username": "Slowdays"},
        "timestamp": "2026-05-09T16:00:00Z",
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


class TestSignature:
    def test_soft_mode_skips_when_no_secret(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "")
        from src.app.config import get_settings
        get_settings.cache_clear()
        ok, reason = zw.verify_signature(b"{}", signature_header=None)
        assert ok is True
        assert "skipped" in reason

    def test_strict_mode_valid_signature(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "topsecret")
        from src.app.config import get_settings
        get_settings.cache_clear()
        body = b'{"event":"x"}'
        sig = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
        ok, reason = zw.verify_signature(body, signature_header=sig)
        assert ok is True
        assert reason == "verified"

    def test_strict_mode_rejects_missing_header(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "topsecret")
        from src.app.config import get_settings
        get_settings.cache_clear()
        ok, reason = zw.verify_signature(b'{"event":"x"}', signature_header=None)
        assert ok is False
        assert "missing" in reason

    def test_strict_mode_rejects_wrong_signature(self, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "topsecret")
        from src.app.config import get_settings
        get_settings.cache_clear()
        ok, reason = zw.verify_signature(b'{"event":"x"}', signature_header="sha256=deadbeef")
        assert ok is False
        assert "mismatch" in reason


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


class TestExternalId:
    def test_bsuid_takes_priority(self):
        msg = _msg_received(bsuid="bsuid-x", phone="+905551112233")["message"]
        assert zw.derive_external_id(msg) == "zernio_whatsapp_bsuid_bsuid-x"

    def test_falls_back_to_phone_when_no_bsuid(self):
        msg = _msg_received(bsuid=None, phone="+905551112233")["message"]
        assert zw.derive_external_id(msg) == "zernio_whatsapp_phone_+905551112233"

    def test_falls_back_to_sender_id_when_no_phone(self):
        msg = _msg_received(bsuid=None, phone=None, sender_id="abc-id")["message"]
        assert zw.derive_external_id(msg) == "zernio_whatsapp_id_abc-id"

    def test_two_messages_same_user_same_external_id(self):
        a = zw.derive_external_id(_msg_received(text="m1")["message"])
        b = zw.derive_external_id(_msg_received(text="m2")["message"])
        assert a == b


class TestMapToLeadFields:
    def test_whatsapp_incoming_becomes_sicak_lead(self):
        fields = zw.map_to_lead_fields(_msg_received())
        assert fields["kaynak"] == "WhatsApp"
        assert fields["asama"] == "Sicak"
        assert fields["telefon"] == "+905551112233"
        assert fields["ad_soyad"] == "Ide Beach Home"
        assert fields["sektor"] == "Otelcilik"
        assert "Merhaba" in fields["notlar"]
        assert fields["lead_skoru"] == 70  # 20 (Otelcilik) + 20 (WA) + 30 (Sicak)
        assert fields["source_workflow_id"] == "mind_agent_zernio_webhook"

    def test_instagram_maps_to_ig_dm(self):
        fields = zw.map_to_lead_fields(_msg_received(platform="instagram"))
        assert fields["kaynak"] == "IG DM"
        assert "sektor" not in fields  # only WA defaults to Otelcilik

    def test_outgoing_becomes_yeni(self):
        fields = zw.map_to_lead_fields(_msg_received(direction="outgoing"))
        assert fields["asama"] == "Yeni"

    def test_phone_falls_back_from_sender_id(self):
        fields = zw.map_to_lead_fields(_msg_received(phone=None, sender_id="905551112233"))
        assert fields["telefon"] == "+905551112233"


class TestMapToMessageFields:
    def test_uses_platform_message_id_for_idempotency(self):
        f = zw.map_to_message_fields(_msg_received(platform_message_id="wamid.X"), "Lead Y")
        assert f["external_message_id"] == "wamid.X"
        assert f["yon"] == "Gelen"
        assert f["kanal"] == "WhatsApp"
        assert f["lead_adi"] == "Lead Y"

    def test_falls_back_to_envelope_id(self):
        payload = _msg_received(platform_message_id=None)
        f = zw.map_to_message_fields(payload, "Lead")
        # message.id = "msg-1" in helper
        assert f["external_message_id"] == "msg-1"


class TestIsTargetEvent:
    def test_message_received_incoming_is_target(self):
        assert zw.is_target_event(_msg_received()) is True

    def test_message_received_outgoing_is_not_target(self):
        assert zw.is_target_event(_msg_received(direction="outgoing")) is False

    def test_other_events_are_not_target(self):
        assert zw.is_target_event({"event": "post.published"}) is False
        assert zw.is_target_event({"event": "webhook.test"}) is False
        assert zw.is_target_event({}) is False


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_nocodb(monkeypatch):
    client = MagicMock()
    client.upsert_record.return_value = {
        "created": True,
        "record": {"Id": 99, "ad_soyad": "Ide Beach Home", "external_id": "zernio_whatsapp_bsuid_bsuid-123"},
    }
    client.create_record.return_value = {"Id": 200}
    monkeypatch.setattr(zw, "get_nocodb_client", lambda: client)
    yield client


@pytest.fixture
def configured_tables(monkeypatch):
    monkeypatch.setenv("NOCODB_LEADS_TABLE_ID", "leads_tbl")
    monkeypatch.setenv("NOCODB_MESSAGES_TABLE_ID", "msgs_tbl")
    from src.app.config import get_settings
    get_settings.cache_clear()
    yield


class TestHandle:
    def test_skipped_for_non_target_event(self, fake_nocodb, configured_tables):
        result = zw.handle({"event": "post.published"})
        assert result["success"] is True
        assert result["skipped"] is True
        fake_nocodb.upsert_record.assert_not_called()

    def test_target_event_writes_lead_and_message(self, fake_nocodb, configured_tables):
        result = zw.handle(_msg_received())
        assert result["success"] is True
        assert result["lead_id"] == 99
        assert result["created"] is True
        # Lead upsert keyed by external_id
        upsert_calls = fake_nocodb.upsert_record.call_args_list
        assert upsert_calls[0].args[0] == "leads_tbl"
        assert upsert_calls[0].args[1] == "external_id"
        # Message upsert keyed by external_message_id
        assert upsert_calls[1].args[0] == "msgs_tbl"
        assert upsert_calls[1].args[1] == "external_message_id"

    def test_two_messages_same_user_idempotent(self, fake_nocodb, configured_tables):
        # second call returns created=False
        fake_nocodb.upsert_record.side_effect = [
            {"created": True, "record": {"Id": 99, "ad_soyad": "Ide", "external_id": "x"}},
            {"created": True, "record": {"Id": 200}},
            {"created": False, "record": {"Id": 99, "ad_soyad": "Ide", "external_id": "x"}},
            {"created": False, "record": {"Id": 200}},
        ]
        zw.handle(_msg_received(text="m1"))
        result2 = zw.handle(_msg_received(text="m2"))
        assert result2["created"] is False
        assert result2["lead_id"] == 99

    def test_message_log_error_does_not_fail_lead(self, fake_nocodb, configured_tables):
        fake_nocodb.upsert_record.side_effect = [
            {"created": True, "record": {"Id": 99, "ad_soyad": "Ide", "external_id": "x"}},
            RuntimeError("Etkilesimler down"),
        ]
        result = zw.handle(_msg_received())
        assert result["success"] is True
        assert result["lead_id"] == 99
        assert "message_log_error" in result

    def test_missing_leads_table_returns_error(self, fake_nocodb, monkeypatch):
        monkeypatch.delenv("NOCODB_LEADS_TABLE_ID", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        result = zw.handle(_msg_received())
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# FastAPI route
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, fake_nocodb, configured_tables):
    from fastapi.testclient import TestClient
    from src.app.api import app

    return TestClient(app)


class TestRoute:
    def test_happy_path_no_signature_required_in_dev(self, client, monkeypatch):
        monkeypatch.delenv("ZERNIO_WEBHOOK_SECRET", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        resp = client.post("/zernio/webhook", json=_msg_received())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["lead_id"] == 99

    def test_strict_mode_rejects_unsigned(self, client, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "topsecret")
        from src.app.config import get_settings
        get_settings.cache_clear()
        resp = client.post("/zernio/webhook", json=_msg_received())
        assert resp.status_code == 401

    def test_strict_mode_accepts_valid_signature(self, client, monkeypatch):
        monkeypatch.setenv("ZERNIO_WEBHOOK_SECRET", "topsecret")
        from src.app.config import get_settings
        get_settings.cache_clear()
        body = json.dumps(_msg_received()).encode()
        sig = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
        resp = client.post(
            "/zernio/webhook",
            data=body,
            headers={"Content-Type": "application/json", "X-Zernio-Signature": sig},
        )
        assert resp.status_code == 200

    def test_invalid_json_returns_400(self, client, monkeypatch):
        monkeypatch.delenv("ZERNIO_WEBHOOK_SECRET", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        resp = client.post(
            "/zernio/webhook",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_non_target_event_returns_skipped(self, client, monkeypatch):
        monkeypatch.delenv("ZERNIO_WEBHOOK_SECRET", raising=False)
        from src.app.config import get_settings
        get_settings.cache_clear()
        resp = client.post("/zernio/webhook", json={"event": "post.published"})
        assert resp.status_code == 200
        assert resp.json()["skipped"] is True
