"""Tests for NocoDB client - REST API wrapper."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest

from src.infra.errors import ServiceError, classify_error, ErrorCode
from src.infra.nocodb_client import NocoDBClient


@pytest.fixture
def client() -> NocoDBClient:
    return NocoDBClient(base_url="https://noco.example.com", api_token="t-secret")


def _mock_response(status: int, json_body=None, text_body: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text_body or (str(json_body) if json_body else "")
    resp.content = (text_body or "").encode() or b'{"x":1}'
    resp.json = MagicMock(return_value=json_body or {})
    return resp


class TestNocoDBClientCRUD:
    def test_create_record_success(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = (
                _mock_response(200, [{"Id": 42}])
            )
            result = client.create_record("tbl1", {"isim": "Ali"})
            assert result == {"Id": 42}
            # NocoDB v2 expects POST body as ARRAY of records
            kwargs = mock_request.call_args.kwargs
            assert kwargs["json"] == [{"isim": "Ali"}]

    def test_update_record_includes_id_in_body(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = _mock_response(200, [{"Id": 7}])
            client.update_record("tbl1", 7, {"asama": "Sicak"})
            args, kwargs = mock_request.call_args
            assert args[0] == "PATCH"
            # NocoDB v2 expects PATCH body as ARRAY of {Id, ...fields}
            assert kwargs["json"] == [{"Id": 7, "asama": "Sicak"}]

    def test_list_records_passes_where_filter(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = _mock_response(200, {"list": []})
            client.list_records("tbl1", where="(asama,eq,Sicak)", limit=10)
            kwargs = mock_request.call_args.kwargs
            assert kwargs["params"]["where"] == "(asama,eq,Sicak)"
            assert kwargs["params"]["limit"] == 10

    def test_get_record_uses_id_path(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = _mock_response(200, {"Id": 5})
            client.get_record("tbl1", 5)
            args, _ = mock_request.call_args
            assert args[0] == "GET"
            assert args[1].endswith("/tbl1/records/5")


class TestNocoDBClientUpsert:
    """Idempotent upsert: lookup by unique field, then INSERT or PATCH."""

    def test_find_by_field_returns_first_match(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = _mock_response(
                200, {"list": [{"Id": 9, "external_id": "ext-1"}]}
            )
            result = client.find_by_field("tbl1", "external_id", "ext-1")
            assert result == {"Id": 9, "external_id": "ext-1"}
            kwargs = mock_request.call_args.kwargs
            assert kwargs["params"]["where"] == "(external_id,eq,ext-1)"
            assert kwargs["params"]["limit"] == 1

    def test_find_by_field_returns_none_when_empty(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.request.return_value = (
                _mock_response(200, {"list": []})
            )
            assert client.find_by_field("tbl1", "external_id", "missing") is None

    def test_upsert_record_inserts_when_not_found(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.side_effect = [
                _mock_response(200, {"list": []}),  # lookup → empty
                _mock_response(200, [{"Id": 11, "external_id": "ext-9"}]),  # POST array
            ]
            result = client.upsert_record(
                "tbl1", "external_id", {"external_id": "ext-9", "isim": "X"}
            )
            assert result["created"] is True
            assert result["record"]["Id"] == 11
            # Two HTTP calls: GET then POST
            methods = [call.args[0] for call in mock_request.call_args_list]
            assert methods == ["GET", "POST"]

    def test_upsert_record_patches_when_found(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.side_effect = [
                _mock_response(200, {"list": [{"Id": 7, "external_id": "ext-9"}]}),
                _mock_response(200, [{"Id": 7}]),  # PATCH array
            ]
            result = client.upsert_record(
                "tbl1", "external_id", {"external_id": "ext-9", "skor": 90}
            )
            assert result["created"] is False
            assert result["record"]["Id"] == 7
            methods = [call.args[0] for call in mock_request.call_args_list]
            assert methods == ["GET", "PATCH"]
            # PATCH body must include the existing Id (as array of records)
            patch_body = mock_request.call_args_list[1].kwargs["json"]
            assert patch_body == [{"Id": 7, "external_id": "ext-9", "skor": 90}]

    def test_upsert_record_raises_if_unique_field_missing(self, client: NocoDBClient):
        with pytest.raises(ValueError, match="external_id"):
            client.upsert_record("tbl1", "external_id", {"isim": "no key"})


class TestNocoDBClientErrors:
    def test_http_500_raises_service_error_with_status(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.request.return_value = (
                _mock_response(500, text_body="server error")
            )
            with pytest.raises(ServiceError) as exc_info:
                client.create_record("tbl1", {"x": 1})
            assert exc_info.value.status_code == 500
            assert exc_info.value.service == "nocodb"

    def test_timeout_raises_service_error(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.request.side_effect = (
                httpx.TimeoutException("read timeout")
            )
            with pytest.raises(ServiceError):
                client.create_record("tbl1", {"x": 1})

    def test_classify_error_maps_429_to_rate_limit(self, client: NocoDBClient):
        exc = ServiceError("API Error 429: too many", status_code=429, service="nocodb")
        result = classify_error(exc, "nocodb")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True
        assert result["retry_after_seconds"] == 60
        assert result["service"] == "nocodb"

    def test_classify_error_maps_404_to_not_found(self, client: NocoDBClient):
        exc = ServiceError("API Error 404", status_code=404, service="nocodb")
        result = classify_error(exc, "nocodb")
        assert result["error_code"] == ErrorCode.NOT_FOUND
        assert result["retryable"] is False
