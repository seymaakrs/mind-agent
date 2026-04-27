"""
customer_tools tests.

Tools:
- customer_search_leads: lead listele + optional asama filtresi
- customer_get_lead: tek lead oku
- customer_get_pipeline_summary: pipeline ozeti

Davranis:
- Her tool feature flag kontrolu yapar (capability gate). Kapali ise
  feature_disabled doner, NocoDB'ye gitmez.
- Whitelist ihlali olusabilecek input'lar erken reddedilir.
- NocoDBClient hata donerse mind-agent ServiceError pattern korunur.
"""
from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-fake-key")

from unittest.mock import AsyncMock, patch

import pytest

from src.app.config import (
    CustomerAgentFlags,
    clear_customer_agent_flags_cache,
)
from src.tools.customer_tools import (
    _customer_get_lead_impl,
    _customer_get_pipeline_summary_impl,
    _customer_search_leads_impl,
)


@pytest.fixture(autouse=True)
def reset_flags():
    clear_customer_agent_flags_cache()
    yield
    clear_customer_agent_flags_cache()


def _flags(**kwargs) -> CustomerAgentFlags:
    """Test helper: belirli alt-flag'leri acik bir flag seti uretir."""
    defaults = {"enabled": True}
    defaults.update(kwargs)
    return CustomerAgentFlags(**defaults)


# ---------------------------------------------------------------------------
# Capability gate (feature flag) — ana savunma
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_leads_blocked_when_master_off():
    """enabled=False → feature_disabled, NocoDB'ye gidilmez."""
    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=CustomerAgentFlags(enabled=False, can_read_leads=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client"
        ) as mock_build:
            result = await _customer_search_leads_impl(asama=None, limit=10)

    assert result["success"] is False
    assert result["error_code"] == "FEATURE_DISABLED"
    mock_build.assert_not_called()


@pytest.mark.asyncio
async def test_search_leads_blocked_when_subflag_off():
    """canReadLeads=False → feature_disabled, NocoDB'ye gidilmez."""
    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_leads=False),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client"
        ) as mock_build:
            result = await _customer_search_leads_impl(asama=None, limit=10)

    assert result["success"] is False
    assert result["error_code"] == "FEATURE_DISABLED"
    mock_build.assert_not_called()


@pytest.mark.asyncio
async def test_get_pipeline_summary_blocked_when_subflag_off():
    """canReadPipeline=False → feature_disabled."""
    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_pipeline=False),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client"
        ) as mock_build:
            result = await _customer_get_pipeline_summary_impl()

    assert result["success"] is False
    assert result["error_code"] == "FEATURE_DISABLED"
    mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# Mutlu yol (flag'ler acik)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_leads_returns_summarized_records():
    """Bayrak acik → NocoDB cevabi LLM-dostu ozete cevirilir."""
    fake_client = AsyncMock()
    fake_client.list_leads = AsyncMock(
        return_value={
            "success": True,
            "records": [
                {"Id": 1, "ad_soyad": "Ahmet", "asama": "Sicak", "lead_skoru": 80},
                {"Id": 2, "ad_soyad": "Ayse", "asama": "Yeni", "lead_skoru": 30},
            ],
            "page_info": {"totalRows": 2, "page": 1, "pageSize": 10},
        }
    )

    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_leads=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client",
            return_value=fake_client,
        ):
            result = await _customer_search_leads_impl(asama=None, limit=10)

    assert result["success"] is True
    assert result["count"] == 2
    assert result["leads"][0]["ad_soyad"] == "Ahmet"


@pytest.mark.asyncio
async def test_search_leads_with_asama_filter_passes_where():
    """asama parametresi NocoDB 'where' clause'una donusur."""
    fake_client = AsyncMock()
    fake_client.list_leads = AsyncMock(
        return_value={"success": True, "records": [], "page_info": {}}
    )

    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_leads=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client",
            return_value=fake_client,
        ):
            await _customer_search_leads_impl(asama="Sicak", limit=10)

    call_kwargs = fake_client.list_leads.call_args.kwargs
    assert call_kwargs.get("where") == "(asama,eq,Sicak)"


@pytest.mark.asyncio
async def test_get_lead_returns_record():
    """Bayrak acik → tek lead doner."""
    fake_client = AsyncMock()
    fake_client.get_lead = AsyncMock(
        return_value={"success": True, "record": {"Id": 5, "ad_soyad": "Mehmet"}}
    )

    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_leads=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client",
            return_value=fake_client,
        ):
            result = await _customer_get_lead_impl(lead_id=5)

    assert result["success"] is True
    assert result["lead"]["Id"] == 5


@pytest.mark.asyncio
async def test_get_pipeline_summary_aggregates_stages():
    """Pipeline ozeti asamalara gore sayim doner."""
    fake_client = AsyncMock()
    fake_client.list_pipeline = AsyncMock(
        return_value={
            "success": True,
            "records": [
                {"asama": "Discovery Call", "tutar": 29000},
                {"asama": "Discovery Call", "tutar": 14900},
                {"asama": "Teklif Gonderildi", "tutar": 29000},
                {"asama": "Kazanildi", "tutar": 29000},
            ],
            "page_info": {"totalRows": 4},
        }
    )

    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_pipeline=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client",
            return_value=fake_client,
        ):
            result = await _customer_get_pipeline_summary_impl()

    assert result["success"] is True
    assert result["total_records"] == 4
    assert result["by_stage"]["Discovery Call"] == 2
    assert result["by_stage"]["Kazanildi"] == 1


# ---------------------------------------------------------------------------
# NocoDB hata yansitma (ServiceError korunur)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_leads_propagates_nocodb_error():
    """NocoDB hata donerse aynen yansir."""
    fake_client = AsyncMock()
    fake_client.list_leads = AsyncMock(
        return_value={
            "success": False,
            "error_code": "NETWORK_ERROR",
            "error": "connection refused",
            "retryable": True,
            "user_message_tr": "CRM'e su an erisilemiyor.",
            "service": "nocodb",
        }
    )

    with patch(
        "src.tools.customer_tools.get_customer_agent_flags",
        return_value=_flags(can_read_leads=True),
    ):
        with patch(
            "src.tools.customer_tools._build_nocodb_client",
            return_value=fake_client,
        ):
            result = await _customer_search_leads_impl(asama=None, limit=10)

    assert result["success"] is False
    assert result["error_code"] == "NETWORK_ERROR"
    assert result["retryable"] is True


# ---------------------------------------------------------------------------
# Public surface — tool list
# ---------------------------------------------------------------------------


def test_get_customer_tools_returns_three_tools():
    """get_customer_tools() 3 tool doner."""
    from src.tools.customer_tools import get_customer_tools

    tools = get_customer_tools()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {
        "customer_search_leads",
        "customer_get_lead",
        "customer_get_pipeline_summary",
    }
