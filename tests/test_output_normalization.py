"""
Tests for action output normalization in logging_hooks and task_logger.

Ensures all action outputs have a predictable shape (success, type fields)
so the Next.js panel can safely render them without crashing.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from src.app.logging_hooks import CliLoggingHooks
from src.infra.task_logger import TaskLogger


# ── CliLoggingHooks output normalization ──────────────────────────────


class TestLoggingHooksOutputNormalization:
    """Verify on_tool_end normalizes all output formats for Firebase."""

    def _make_hooks(self) -> CliLoggingHooks:
        """Create hooks with a mock task_logger."""
        hooks = CliLoggingHooks(echo=False)
        hooks.task_logger = MagicMock(spec=TaskLogger)
        return hooks

    def _make_context_agent_tool(self):
        """Create mock context, agent, and tool."""
        context = MagicMock()
        agent = MagicMock()
        agent.name = "test_agent"
        tool = MagicMock()
        tool.name = "test_tool"
        return context, agent, tool

    @pytest.mark.asyncio
    async def test_dict_result_passed_through(self):
        """Dict results (from direct tools) should be passed as-is."""
        hooks = self._make_hooks()
        ctx, agent, tool = self._make_context_agent_tool()

        result = {"success": True, "public_url": "https://example.com/img.png", "path": "images/test.png"}
        await hooks.on_tool_end(ctx, agent, tool, result)

        call_args = hooks.task_logger.log_action.call_args
        output_data = call_args.kwargs["output_data"]
        assert output_data == result
        assert output_data["success"] is True
        assert "type" not in output_data  # Direct tool dicts don't get type field

    @pytest.mark.asyncio
    async def test_string_result_normalized_with_success(self):
        """String results (from agent wrappers) should get success=True and type='agent_output'."""
        hooks = self._make_hooks()
        ctx, agent, tool = self._make_context_agent_tool()

        result = "Image generated successfully at images/test.png"
        await hooks.on_tool_end(ctx, agent, tool, result)

        call_args = hooks.task_logger.log_action.call_args
        output_data = call_args.kwargs["output_data"]
        assert output_data["success"] is True
        assert output_data["type"] == "agent_output"
        assert output_data["result"] == result

    @pytest.mark.asyncio
    async def test_error_string_normalized_with_success_false(self):
        """String results containing 'error' should get success=False."""
        hooks = self._make_hooks()
        ctx, agent, tool = self._make_context_agent_tool()

        result = "Error: Failed to generate image"
        await hooks.on_tool_end(ctx, agent, tool, result)

        call_args = hooks.task_logger.log_action.call_args
        output_data = call_args.kwargs["output_data"]
        assert output_data["success"] is False
        assert output_data["type"] == "agent_output"

    @pytest.mark.asyncio
    async def test_dict_error_result_passed_through(self):
        """Dict results with success=False should be passed as-is."""
        hooks = self._make_hooks()
        ctx, agent, tool = self._make_context_agent_tool()

        result = {"success": False, "error": "API rate limit exceeded"}
        await hooks.on_tool_end(ctx, agent, tool, result)

        call_args = hooks.task_logger.log_action.call_args
        output_data = call_args.kwargs["output_data"]
        assert output_data["success"] is False


# ── TaskLogger sanitization ───────────────────────────────────────────


class TestTaskLoggerSanitization:
    """Verify _sanitize_for_firestore protects URL fields from truncation."""

    def _make_logger(self) -> TaskLogger:
        """Create a TaskLogger without Firebase connection."""
        with patch("src.infra.task_logger.get_document_client"):
            return TaskLogger(business_id="test_biz")

    def test_long_url_not_truncated(self):
        """URL fields should never be truncated regardless of length."""
        logger = self._make_logger()
        long_url = "https://storage.googleapis.com/" + "a" * 2000
        data = {"public_url": long_url, "path": "images/test.png"}

        result = logger._sanitize_for_firestore(data)
        assert result["public_url"] == long_url  # Full URL preserved

    def test_long_regular_field_truncated(self):
        """Non-protected string fields over 1000 chars should be truncated."""
        logger = self._make_logger()
        long_text = "x" * 2000
        data = {"description": long_text}

        result = logger._sanitize_for_firestore(data)
        assert len(result["description"]) < 2000
        assert result["description"].endswith("...[truncated]")

    def test_protected_fields_list(self):
        """All common URL/ID fields should be in the protected set."""
        expected_protected = {
            "public_url", "url", "path", "post_url", "video_url",
            "image_url", "permalink", "post_id", "media_id",
        }
        assert expected_protected.issubset(TaskLogger._PROTECTED_FIELDS)

    def test_nested_dict_sanitized(self):
        """Nested dicts should also be sanitized recursively."""
        logger = self._make_logger()
        data = {
            "outer": {
                "public_url": "https://example.com/" + "a" * 2000,
                "description": "x" * 2000,
            }
        }

        result = logger._sanitize_for_firestore(data)
        # URL preserved in nested dict
        assert len(result["outer"]["public_url"]) > 1000
        # Description truncated in nested dict
        assert result["outer"]["description"].endswith("...[truncated]")

    def test_result_field_not_protected(self):
        """The 'result' field (agent output text) should still be truncated."""
        logger = self._make_logger()
        long_result = "Agent completed: " + "x" * 2000
        data = {"result": long_result, "success": True, "type": "agent_output"}

        result = logger._sanitize_for_firestore(data)
        assert result["result"].endswith("...[truncated]")
        assert result["success"] is True  # success preserved
