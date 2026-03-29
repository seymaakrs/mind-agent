from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import IO, TYPE_CHECKING, Any

from agents.lifecycle import RunHooksBase

if TYPE_CHECKING:
    from src.infra.task_logger import TaskLogger


class CliLoggingHooks(RunHooksBase):
    """Detailed CLI logs for agent/tool lifecycle; mirrors to a logfile."""

    def __init__(
        self,
        log_dir: str = "logs",
        file_prefix: str = "run",
        *,
        echo: bool = True,
        task_logger: TaskLogger | None = None,
        verbose: bool = True,
        progress_queue: asyncio.Queue | None = None,
    ) -> None:
        self.log_dir = log_dir
        self.file_prefix = file_prefix
        self.echo = echo
        self.log_path: str | None = None
        self._fh: IO[str] | None = None
        self.task_logger = task_logger
        self.verbose = verbose
        self.progress_queue = progress_queue

        # Store pending tool calls from LLM response
        self._pending_tool_calls: dict[str, dict[str, Any]] = {}

        try:
            os.makedirs(self.log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.log_path = os.path.join(self.log_dir, f"{self.file_prefix}-{timestamp}.log")
            self._fh = open(self.log_path, "a", encoding="utf-8")
            if self.echo:
                print(f"[log] writing session logs to {self.log_path}")
        except Exception as exc:
            if self.echo:
                print(f"[log] file logging disabled: {exc}")
            self._fh = None

    def _send_progress(self, event_type: str, message: str, data: dict | None = None) -> None:
        """Send progress event to queue (non-blocking)."""
        if self.progress_queue:
            try:
                self.progress_queue.put_nowait({
                    "type": "progress",
                    "event": event_type,
                    "message": message,
                    "data": data or {},
                    "timestamp": datetime.now().isoformat(),
                })
            except asyncio.QueueFull:
                pass  # Drop if queue is full

    def _write_only(self, message: str) -> None:
        """Write to file only (no echo)."""
        if self._fh:
            try:
                self._fh.write(message + "\n")
                self._fh.flush()
            except Exception:
                pass

    def _log(self, message: str) -> None:
        """Write to both console (if echo) and file."""
        if self.echo:
            try:
                print(message)
            except UnicodeEncodeError:
                enc = sys.stdout.encoding or "utf-8"
                safe = message.encode(enc, errors="backslashreplace").decode(
                    enc, errors="ignore"
                )
                print(safe)
        self._write_only(message)

    def _format_json(self, data: Any, max_length: int = 2000) -> str:
        """Format data as pretty JSON, truncated if needed."""
        try:
            if isinstance(data, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(data)
                    formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    formatted = data
            else:
                formatted = json.dumps(data, ensure_ascii=False, indent=2, default=str)

            if len(formatted) > max_length:
                return formatted[:max_length] + "\n... [truncated]"
            return formatted
        except Exception:
            return str(data)[:max_length]

    def log_task(self, task: str) -> None:
        """Write the incoming task to the logfile at the top of the session."""
        task_text = (task or "").rstrip("\n")
        self._write_only("=" * 80)
        self._write_only(f"[TASK] {datetime.now().isoformat()}")
        self._write_only("=" * 80)
        if task_text:
            self._write_only(task_text)
        self._write_only("=" * 80)

    async def on_agent_start(self, context, agent) -> None:
        # Get model info
        model_info = getattr(agent, 'model', None)
        model_str = ""
        if model_info:
            # Model could be string or ModelSettings object
            if isinstance(model_info, str):
                model_str = f" [model: {model_info}]"
            elif hasattr(model_info, 'model'):
                model_str = f" [model: {model_info.model}]"
            else:
                model_str = f" [model: {model_info}]"

        self._log(f"\n[AGENT:START] {agent.name}{model_str}")
        self._write_only("-" * 40)

        # Send progress
        self._send_progress("agent_start", f"🤖 {agent.name} agent başladı")

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._log(f"[LLM:START] {agent.name}")

        if self.verbose and input_items:
            self._write_only(f"[LLM:INPUT] {len(input_items)} items")
            for i, item in enumerate(input_items[-3:]):  # Last 3 items
                item_str = self._format_json(item, max_length=500)
                self._write_only(f"  [{i}] {item_str}")

    async def on_llm_end(self, context, agent, response) -> None:
        self._log(f"[LLM:END] {agent.name}")

        # Extract tool calls from response for later use
        if response and response.output:
            for item in response.output:
                # Check if it's a tool call
                if hasattr(item, 'raw_item'):
                    raw = item.raw_item
                    if hasattr(raw, 'name') and hasattr(raw, 'arguments'):
                        call_id = getattr(raw, 'call_id', None) or raw.name
                        try:
                            args = json.loads(raw.arguments) if isinstance(raw.arguments, str) else raw.arguments
                        except (json.JSONDecodeError, TypeError):
                            args = raw.arguments

                        self._pending_tool_calls[raw.name] = {
                            "call_id": call_id,
                            "name": raw.name,
                            "arguments": args,
                        }

                        if self.verbose:
                            self._write_only(f"[LLM:TOOL_CALL] {raw.name}")
                            self._write_only(f"  Arguments: {self._format_json(args, max_length=1000)}")

    async def on_tool_start(self, context, agent, tool) -> None:
        self._log(f"[TOOL:START] {agent.name} -> {tool.name}")

        # Log input from pending tool calls
        if tool.name in self._pending_tool_calls:
            call_info = self._pending_tool_calls[tool.name]
            self._write_only(f"[TOOL:INPUT] {tool.name}")
            self._write_only(self._format_json(call_info.get("arguments", {}), max_length=2000))

        # Send progress
        self._send_progress("tool_start", f"🔧 {tool.name} çalıştırılıyor...", {"tool": tool.name})

        # Fire-and-forget: update active task current_step
        if self.task_logger:
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self.task_logger.update_step, tool.name)
            except Exception:
                pass

    async def on_tool_end(self, context, agent, tool, result) -> None:
        # Get input from pending calls
        input_data = None
        if tool.name in self._pending_tool_calls:
            input_data = self._pending_tool_calls.pop(tool.name, {}).get("arguments")

        # Determine if error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get("success") is False
        elif isinstance(result, str) and "error" in result.lower():
            is_error = True

        if is_error:
            self._log(f"[TOOL:ERROR] {agent.name} <- {tool.name}")
            self._write_only(f"[TOOL:OUTPUT] {tool.name} (ERROR)")
            self._write_only(self._format_json(result, max_length=3000))
            # Send progress
            error_code = result.get("error_code") if isinstance(result, dict) else None
            self._send_progress("tool_error", f"❌ {tool.name} hata verdi", {
                "tool": tool.name,
                "error_code": error_code,
                "retryable": result.get("retryable") if isinstance(result, dict) else None,
                "service": result.get("service") if isinstance(result, dict) else None,
            })
        else:
            self._log(f"[TOOL:END] {agent.name} <- {tool.name}")
            self._write_only(f"[TOOL:OUTPUT] {tool.name}")
            self._write_only(self._format_json(result, max_length=2000))
            # Send progress
            self._send_progress("tool_end", f"✅ {tool.name} tamamlandı", {"tool": tool.name})

        # Firebase logging
        if self.task_logger:
            if isinstance(result, dict):
                output_data = result
            else:
                # Normalize non-dict results (e.g. agent wrapper string outputs)
                # so every action.output has a predictable shape for the panel
                output_data = {
                    "result": str(result),
                    "success": not is_error,
                    "type": "agent_output",
                }
            self.task_logger.log_action(
                tool=tool.name,
                input_data=input_data,
                output_data=output_data,
            )

    async def on_handoff(self, context, from_agent, to_agent) -> None:
        self._log(f"[HANDOFF] {from_agent.name} -> {to_agent.name}")
        # Send progress
        self._send_progress("handoff", f"🔄 {from_agent.name} → {to_agent.name} geçiş yapılıyor")

    async def on_agent_end(self, context, agent, output) -> None:
        self._log(f"[AGENT:END] {agent.name}")
        self._write_only(f"[AGENT:OUTPUT] {agent.name}")

        # Format output
        if isinstance(output, str):
            preview = output[:1000] + "..." if len(output) > 1000 else output
        else:
            preview = self._format_json(output, max_length=1000)

        self._write_only(preview)
        self._write_only("-" * 40)

        # Send progress
        self._send_progress("agent_end", f"✅ {agent.name} agent tamamlandı")

    def close(self) -> None:
        if self._fh:
            try:
                self._fh.close()
            except Exception:
                pass
            finally:
                self._fh = None

    def __del__(self) -> None:
        self.close()


__all__ = ["CliLoggingHooks"]
