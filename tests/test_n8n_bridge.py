"""Tests for n8n köprü tool'lari (mind-agent <-> n8n.cloud)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.tools import n8n_bridge_tools as bt  # noqa: E402
from src.tools.n8n_registry import N8N_REGISTRY, find_workflow  # noqa: E402


class TestRegistry:
    def test_find_workflow_exists(self):
        wf = find_workflow("drive_upload")
        assert wf is not None
        assert wf.webhook_path == "drive/upload"

    def test_find_workflow_case_insensitive(self):
        assert find_workflow("DRIVE_UPLOAD") is not None
        assert find_workflow("Itiraz_Agent") is not None

    def test_find_workflow_missing(self):
        assert find_workflow("does_not_exist") is None

    def test_registry_has_core_entries(self):
        names = {wf.name for wf in N8N_REGISTRY}
        assert "drive_upload" in names
        assert "sheets_read" in names
        assert "itiraz_agent" in names
        assert "bekci_alert" in names


class TestListN8nWorkflows:
    @pytest.mark.asyncio
    async def test_returns_all_known(self):
        result = await bt._list_n8n_workflows_impl()
        assert result["success"] is True
        assert result["count"] == len(N8N_REGISTRY)
        # Every entry has the expected keys
        for item in result["workflows"]:
            assert {"name", "workflow_id", "webhook_path", "description"} <= set(item)


class TestCallN8nWorkflow:
    @pytest.mark.asyncio
    async def test_rejects_empty_name(self):
        result = await bt._call_n8n_workflow_impl("", body={})
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_rejects_unknown_workflow(self):
        result = await bt._call_n8n_workflow_impl("unknown_xyz", body={})
        assert result["success"] is False
        assert result["error_code"] == "NOT_FOUND"
        assert "drive_upload" in result["user_message_tr"]  # bilinenleri sayar

    @pytest.mark.asyncio
    async def test_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("N8N_BASE_URL", raising=False)
        result = await bt._call_n8n_workflow_impl("drive_upload", body={"x": 1})
        assert result["success"] is False
        assert "N8N_BASE_URL" in result["error"]

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self, monkeypatch):
        monkeypatch.setenv("N8N_BASE_URL", "https://mindidai.app.n8n.cloud")

        captured = {}

        class FakeResponse:
            status_code = 200
            def json(self): return {"workflow_run_id": "abc"}
            text = ""

        class FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def post(self, url, json=None):
                captured["url"] = url
                captured["body"] = json
                return FakeResponse()
            async def get(self, url, params=None):
                captured["url"] = url
                captured["params"] = params
                return FakeResponse()

        monkeypatch.setattr(bt.httpx, "AsyncClient", FakeClient)

        result = await bt._call_n8n_workflow_impl(
            "drive_upload", body={"filename": "x.png"}
        )
        assert result["success"] is True
        assert captured["url"] == "https://mindidai.app.n8n.cloud/webhook/drive/upload"
        assert captured["body"] == {"filename": "x.png"}

    @pytest.mark.asyncio
    async def test_get_method_uses_params(self, monkeypatch):
        monkeypatch.setenv("N8N_BASE_URL", "https://mindidai.app.n8n.cloud")

        captured = {}

        class FakeResponse:
            status_code = 200
            def json(self): return {"data": []}
            text = ""

        class FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def get(self, url, params=None):
                captured["url"] = url
                captured["params"] = params
                return FakeResponse()
            async def post(self, *a, **kw):
                raise AssertionError("should use GET")

        monkeypatch.setattr(bt.httpx, "AsyncClient", FakeClient)

        # drive_list is registered as GET
        result = await bt._call_n8n_workflow_impl("drive_list", body={"folder_id": "F1"})
        assert result["success"] is True
        assert captured["params"] == {"folder_id": "F1"}

    @pytest.mark.asyncio
    async def test_upstream_error_is_reported(self, monkeypatch):
        monkeypatch.setenv("N8N_BASE_URL", "https://mindidai.app.n8n.cloud")

        class FakeResponse:
            status_code = 500
            text = "Internal Server Error"

        class FakeClient:
            def __init__(self, *a, **kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def post(self, *a, **kw): return FakeResponse()
            async def get(self, *a, **kw): return FakeResponse()

        monkeypatch.setattr(bt.httpx, "AsyncClient", FakeClient)

        result = await bt._call_n8n_workflow_impl("itiraz_agent", body={"mesaj": "x"})
        assert result["success"] is False
        assert result["error_code"] == "UPSTREAM"
        assert result["status_code"] == 500


class TestN8nWorkflowHealth:
    @pytest.mark.asyncio
    async def test_known_workflow_with_base_url(self, monkeypatch):
        monkeypatch.setenv("N8N_BASE_URL", "https://mindidai.app.n8n.cloud")
        result = await bt._n8n_workflow_health_impl("itiraz_agent")
        assert result["success"] is True
        assert result["configured"] is True
        assert result["workflow_id"] == "9nTdKNPLCjo8DKfE"

    @pytest.mark.asyncio
    async def test_known_workflow_missing_base_url(self, monkeypatch):
        monkeypatch.delenv("N8N_BASE_URL", raising=False)
        result = await bt._n8n_workflow_health_impl("itiraz_agent")
        assert result["success"] is True
        assert result["configured"] is False

    @pytest.mark.asyncio
    async def test_unknown_workflow(self):
        result = await bt._n8n_workflow_health_impl("xxx")
        assert result["success"] is False
        assert result["error_code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_bekci_alert_not_yet_configured(self, monkeypatch):
        # bekci_alert has empty workflow_id in registry (Beyza will create it
        # before going live). Health reports "not configured" even if base URL set.
        monkeypatch.setenv("N8N_BASE_URL", "https://mindidai.app.n8n.cloud")
        result = await bt._n8n_workflow_health_impl("bekci_alert")
        assert result["success"] is True
        assert result["configured"] is False  # workflow_id is empty


class TestToolRegistration:
    def test_orchestrator_picks_up_bridge_tools(self):
        from src.tools.orchestrator import get_orchestrator_tools

        names = {getattr(t, "name", None) for t in get_orchestrator_tools()}
        assert "list_n8n_workflows" in names
        assert "call_n8n_workflow" in names
        assert "n8n_workflow_health" in names
