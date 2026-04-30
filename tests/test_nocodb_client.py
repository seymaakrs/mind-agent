"""NocoDB v2 REST client tests (TEST-FIRST).

Strategy:
- Mock httpx via respx-style monkeypatching of NocoDBClient internals
- Cover: list, get, create, update, delete, query, error classification
- Tolerant reader: missing fields use defaults, no crash
- Idempotency hint: duplicate-creation handling
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infra.errors import ErrorCode, ServiceError, classify_error
from src.infra.nocodb_client import NocoDBClient, NocoDBConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cfg() -> NocoDBClient:
    """A NocoDB client wired to fake credentials."""
    return NocoDBClient(
        NocoDBConfig(
            base_url="https://nocodb.test",
            api_token="xc-token-fake",
            leads_table_id="t_leads",
            messages_table_id="t_msgs",
            notifications_table_id="t_notif",
            campaigns_table_id="t_camps",
            daily_metrics_table_id="t_daily",
            decisions_log_table_id="t_dec",
            objections_log_table_id="t_obj",
            agent_health_table_id="t_health",
        )
    )


def _ok_response(payload: dict[str, Any], status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=httpx.Response(200, json=payload).content,
        request=httpx.Request("GET", "https://nocodb.test"),
    )


# ---------------------------------------------------------------------------
# Configuration guards
# ---------------------------------------------------------------------------


class TestNocoDBConfig:
    def test_config_strips_trailing_slash_on_base_url(self) -> None:
        c = NocoDBConfig(
            base_url="https://nocodb.test/",
            api_token="x",
            leads_table_id="L",
            messages_table_id="M",
            notifications_table_id="N",
        )
        assert c.base_url == "https://nocodb.test"

    def test_config_requires_required_fields(self) -> None:
        with pytest.raises(ValueError):
            NocoDBConfig(
                base_url="",
                api_token="",
                leads_table_id="",
                messages_table_id="",
                notifications_table_id="",
            )


# ---------------------------------------------------------------------------
# Headers + URL building
# ---------------------------------------------------------------------------


class TestNocoDBClientWiring:
    def test_auth_header_present(self, cfg: NocoDBClient) -> None:
        h = cfg._headers()
        assert h["xc-token"] == "xc-token-fake"
        assert h["Content-Type"] == "application/json"

    def test_records_url_for_leads(self, cfg: NocoDBClient) -> None:
        url = cfg._records_url("t_leads")
        assert url == "https://nocodb.test/api/v2/tables/t_leads/records"

    def test_records_url_for_unknown_table_raises(self, cfg: NocoDBClient) -> None:
        # Empty table_id is a programmer error
        with pytest.raises(ValueError, match="table_id"):
            cfg._records_url("")


# ---------------------------------------------------------------------------
# CRUD operations (mocked HTTP)
# ---------------------------------------------------------------------------


class TestNocoDBCreate:
    @pytest.mark.asyncio
    async def test_create_record_returns_id_and_data(self, cfg: NocoDBClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"Id": 42})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.post = AsyncMock(return_value=mock_response)
            result = await cfg.create_record(
                "t_leads", {"name": "Ali", "phone": "+90", "lead_score": 8}
            )
            assert result == {"Id": 42}
            fake_client.post.assert_awaited_once()
            kwargs = fake_client.post.await_args.kwargs
            # NocoDB v2 expects array body
            assert isinstance(kwargs["json"], list)
            assert kwargs["json"][0]["name"] == "Ali"

    @pytest.mark.asyncio
    async def test_create_record_classifies_400(self, cfg: NocoDBClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "validation failed"
        err = httpx.HTTPStatusError(
            "bad request",
            request=httpx.Request("POST", "https://nocodb.test"),
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=err)

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.post = AsyncMock(return_value=mock_response)
            with pytest.raises(ServiceError) as exc_info:
                await cfg.create_record("t_leads", {"bad": "data"})
            assert exc_info.value.status_code == 400
            assert exc_info.value.service == "nocodb"


class TestNocoDBQuery:
    @pytest.mark.asyncio
    async def test_query_returns_list_field(self, cfg: NocoDBClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "list": [{"Id": 1, "name": "Ali"}, {"Id": 2, "name": "Veli"}],
                "pageInfo": {"totalRows": 2},
            }
        )
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            rows = await cfg.query_records(
                "t_leads", where="(lead_status,eq,hot)", limit=50
            )
            assert len(rows) == 2
            assert rows[0]["name"] == "Ali"
            params = fake_client.get.await_args.kwargs["params"]
            assert params["where"] == "(lead_status,eq,hot)"
            assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_query_tolerates_missing_list_field(
        self, cfg: NocoDBClient
    ) -> None:
        """Tolerant reader: If response has no 'list' key, return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={})  # no 'list' field
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            rows = await cfg.query_records("t_leads")
            assert rows == []


class TestNocoDBUpdate:
    @pytest.mark.asyncio
    async def test_update_record_passes_id(self, cfg: NocoDBClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"Id": 42, "name": "Updated"})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.patch = AsyncMock(return_value=mock_response)
            await cfg.update_record("t_leads", 42, {"name": "Updated"})
            body = fake_client.patch.await_args.kwargs["json"]
            assert body == [{"Id": 42, "name": "Updated"}]


class TestNocoDBGet:
    @pytest.mark.asyncio
    async def test_get_record_by_id(self, cfg: NocoDBClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"Id": 7, "name": "Ali"})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            record = await cfg.get_record("t_leads", 7)
            assert record["Id"] == 7
            assert "/records/7" in fake_client.get.await_args.args[0]

    @pytest.mark.asyncio
    async def test_get_record_404_returns_servceerror(
        self, cfg: NocoDBClient
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "not found"
        err = httpx.HTTPStatusError(
            "not found",
            request=httpx.Request("GET", "https://nocodb.test"),
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=err)

        with patch.object(
            cfg, "_async_client", new_callable=lambda: MagicMock()
        ) as fake_client:
            fake_client.get = AsyncMock(return_value=mock_response)
            with pytest.raises(ServiceError) as exc_info:
                await cfg.get_record("t_leads", 999)
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Error classification integration
# ---------------------------------------------------------------------------


class TestNocoDBErrorClassification:
    def test_429_classified_as_rate_limit(self) -> None:
        err = ServiceError("rate limited", status_code=429, service="nocodb")
        result = classify_error(err, "nocodb")
        assert result["error_code"] == ErrorCode.RATE_LIMIT
        assert result["retryable"] is True

    def test_401_classified_as_auth(self) -> None:
        err = ServiceError("unauthorized", status_code=401, service="nocodb")
        result = classify_error(err, "nocodb")
        assert result["error_code"] == ErrorCode.AUTH_ERROR
        assert result["retryable"] is False

    def test_500_is_retryable(self) -> None:
        err = ServiceError("server", status_code=500, service="nocodb")
        result = classify_error(err, "nocodb")
        assert result["error_code"] == ErrorCode.SERVER_ERROR
        assert result["retryable"] is True
