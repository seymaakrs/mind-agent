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
            MockClient.return_value.__enter__.return_value.request.return_value = (
                _mock_response(200, {"Id": 42, "isim": "Ali"})
            )
            result = client.create_record("tbl1", {"isim": "Ali"})
            assert result == {"Id": 42, "isim": "Ali"}

    def test_update_record_includes_id_in_body(self, client: NocoDBClient):
        with patch("httpx.Client") as MockClient:
            mock_request = MockClient.return_value.__enter__.return_value.request
            mock_request.return_value = _mock_response(200, {"Id": 7})
            client.update_record("tbl1", 7, {"asama": "Sicak"})
            args, kwargs = mock_request.call_args
            assert args[0] == "PATCH"
            assert kwargs["json"] == {"Id": 7, "asama": "Sicak"}

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
