from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import IO, TYPE_CHECKING, Any

from agents.lifecycle import RunHooksBase

if TYPE_CHECKING:
    from src.infra.task_logger import TaskLogger

# Tools that are actually sub-agent wrappers (convention: ends with _agent_tool)
_AGENT_TOOL_SUFFIX = "_agent_tool"


class CliLoggingHooks(RunHooksBase):
    """Detailed CLI logs for agent/tool lifecycle; mirrors to a logfile.

    Sends enriched progress events suitable for n8n-style workflow
    visualisation on the frontend.  Every event carries ``agent_id`` /
    ``parent_agent_id`` so the frontend can build a tree, plus an explicit
    ``status`` field for node state-machines.
    """

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

        # --- Workflow-visualisation state ---
        self._agent_counter: int = 0
        # Stack of agent_ids – top = current active agent
        self._agent_stack: list[str] = []
        # agent.name → most-recent agent_id  (for quick lookup)
        self._agent_id_map: dict[str, str] = {}
        # tool.name → start timestamp (epoch seconds) for duration calc
        self._tool_start_times: dict[str, float] = {}

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

    # ------------------------------------------------------------------
    # Workflow-visualisation helpers
    # ------------------------------------------------------------------

    def _next_agent_id(self, name: str) -> str:
        self._agent_counter += 1
        return f"{name}_{self._agent_counter}"

    @property
    def _current_agent_id(self) -> str | None:
        return self._agent_stack[-1] if self._agent_stack else None

    @property
    def _current_parent_id(self) -> str | None:
        return self._agent_stack[-2] if len(self._agent_stack) >= 2 else None

    @staticmethod
    def _is_agent_call(tool_name: str) -> bool:
        return tool_name.endswith(_AGENT_TOOL_SUFFIX)

    @staticmethod
    def _truncate(text: Any, limit: int = 300) -> str:
        s = str(text) if text is not None else ""
        return s[:limit] + ("…" if len(s) > limit else "")

    def _send_progress(self, event_type: str, message: str, data: dict | None = None) -> None:
        """Send progress event to queue (non-blocking)."""
        if self.progress_queue:
            try:
                self.progress_queue.put_nowait({
                    "type": "progress",
                    "event": event_type,
                    "message": message,
                    **(data or {}),
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
            if isinstance(model_info, str):
                model_str = f" [model: {model_info}]"
            elif hasattr(model_info, 'model'):
                model_str = f" [model: {model_info.model}]"
            else:
                model_str = f" [model: {model_info}]"

        self._log(f"\n[AGENT:START] {agent.name}{model_str}")
        self._write_only("-" * 40)

        # --- Workflow visualisation ---
        agent_id = self._next_agent_id(agent.name)
        parent_id = self._current_agent_id  # whoever is on top of stack is the parent
        self._agent_stack.append(agent_id)
        self._agent_id_map[agent.name] = agent_id

        # Collect tool names available to this agent
        tools_available = [t.name for t in (getattr(agent, "tools", None) or [])]

        self._send_progress("agent_start", f"🤖 {agent.name} agent başladı", {
            "agent_id": agent_id,
            "parent_agent_id": parent_id,
            "agent_name": agent.name,
            "model": model_str.strip(" []") or None,
            "tools_available": tools_available,
            "status": "idle",
        })

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self._log(f"[LLM:START] {agent.name}")

        if self.verbose and input_items:
            self._write_only(f"[LLM:INPUT] {len(input_items)} items")
            for i, item in enumerate(input_items[-3:]):  # Last 3 items
                item_str = self._format_json(item, max_length=500)
                self._write_only(f"  [{i}] {item_str}")

        # --- Workflow: agent is now "thinking" ---
        self._send_progress("llm_start", f"💭 {agent.name} düşünüyor...", {
            "agent_id": self._agent_id_map.get(agent.name),
            "agent_name": agent.name,
            "status": "thinking",
        })

    async def on_llm_end(self, context, agent, response) -> None:
        self._log(f"[LLM:END] {agent.name}")

        # --- Extract tool calls + text message from response ---
        tool_calls_planned: list[dict[str, str]] = []
        llm_message: str | None = None

        if response and response.output:
            for item in response.output:
                if not hasattr(item, 'raw_item'):
                    continue
                raw = item.raw_item

                # Tool call item
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
                    tool_calls_planned.append({
                        "call_id": call_id,
                        "tool": raw.name,
                        "is_agent_call": self._is_agent_call(raw.name),
                    })

                    if self.verbose:
                        self._write_only(f"[LLM:TOOL_CALL] {raw.name}")
                        self._write_only(f"  Arguments: {self._format_json(args, max_length=1000)}")

                # Text message item — LLM's reasoning / decision
                elif hasattr(raw, 'content') and not hasattr(raw, 'name'):
                    content = raw.content
                    if isinstance(content, list):
                        # content can be a list of parts (e.g. [{type:"output_text", text:"..."}])
                        parts = []
                        for part in content:
                            if isinstance(part, str):
                                parts.append(part)
                            elif hasattr(part, 'text'):
                                parts.append(part.text)
                            elif isinstance(part, dict) and 'text' in part:
                                parts.append(part['text'])
                        text = " ".join(parts)
                    elif isinstance(content, str):
                        text = content
                    else:
                        text = str(content)
                    if text.strip():
                        llm_message = text.strip()

        # --- Workflow: agent has "decided" ---
        # Token usage from context
        usage = getattr(context, 'usage', None)
        token_data = {}
        if usage:
            token_data = {
                "total_input_tokens": getattr(usage, 'input_tokens', 0),
                "total_output_tokens": getattr(usage, 'output_tokens', 0),
            }

        self._send_progress("llm_end", f"✅ {agent.name} karar verdi", {
            "agent_id": self._agent_id_map.get(agent.name),
            "agent_name": agent.name,
            "status": "decided",
            "message": self._truncate(llm_message, 500) if llm_message else None,
            "tool_calls_planned": tool_calls_planned or None,
            **token_data,
        })

    async def on_tool_start(self, context, agent, tool) -> None:
        self._log(f"[TOOL:START] {agent.name} -> {tool.name}")

        # Log input from pending tool calls
        input_data: dict[str, Any] = {}
        if tool.name in self._pending_tool_calls:
            call_info = self._pending_tool_calls[tool.name]
            input_data = call_info.get("arguments", {})
            self._write_only(f"[TOOL:INPUT] {tool.name}")
            self._write_only(self._format_json(input_data, max_length=2000))

        # Track start time for duration calculation
        self._tool_start_times[tool.name] = time.monotonic()

        # --- Workflow: build enriched progress event ---
        is_agent = self._is_agent_call(tool.name)

        progress_data: dict[str, Any] = {
            "agent_id": self._agent_id_map.get(agent.name),
            "agent_name": agent.name,
            "tool": tool.name,
            "is_agent_call": is_agent,
            "status": "executing",
        }

        if is_agent:
            # Sub-agent call — show the prompt being passed
            prompt_text = input_data.get("prompt", "")
            progress_data["input_prompt"] = self._truncate(prompt_text, 500)
            progress_data["edge_label"] = self._truncate(prompt_text, 80)
        else:
            # Normal tool — show input parameters
            progress_data["input_preview"] = {
                k: self._truncate(v, 150) for k, v in input_data.items()
            } if input_data else None
            progress_data["edge_label"] = self._truncate(
                ", ".join(f"{k}={v}" for k, v in input_data.items()), 80
            ) if input_data else None

        self._send_progress("tool_start", f"🔧 {tool.name} çalıştırılıyor...", progress_data)

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

        # Calculate duration
        duration_ms: int | None = None
        start_t = self._tool_start_times.pop(tool.name, None)
        if start_t is not None:
            duration_ms = int((time.monotonic() - start_t) * 1000)

        # Determine if error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get("success") is False
        elif isinstance(result, str) and "error" in result.lower():
            is_error = True

        # Build a short output preview for edge labels
        if isinstance(result, dict):
            # Pick the most useful field for preview
            output_preview = (
                result.get("public_url")
                or result.get("error")
                or result.get("result")
                or result.get("message")
                or str(result)
            )
        else:
            output_preview = str(result)

        agent_id = self._agent_id_map.get(agent.name)
        is_agent = self._is_agent_call(tool.name)

        if is_error:
            self._log(f"[TOOL:ERROR] {agent.name} <- {tool.name}")
            self._write_only(f"[TOOL:OUTPUT] {tool.name} (ERROR)")
            self._write_only(self._format_json(result, max_length=3000))

            error_code = result.get("error_code") if isinstance(result, dict) else None
            self._send_progress("tool_error", f"❌ {tool.name} hata verdi", {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "tool": tool.name,
                "is_agent_call": is_agent,
                "status": "error",
                "error_code": error_code,
                "retryable": result.get("retryable") if isinstance(result, dict) else None,
                "user_message_tr": result.get("user_message_tr") if isinstance(result, dict) else None,
                "service": result.get("service") if isinstance(result, dict) else None,
                "output_preview": self._truncate(output_preview, 300),
                "edge_label": self._truncate(output_preview, 80),
                "duration_ms": duration_ms,
            })
        else:
            self._log(f"[TOOL:END] {agent.name} <- {tool.name}")
            self._write_only(f"[TOOL:OUTPUT] {tool.name}")
            self._write_only(self._format_json(result, max_length=2000))

            self._send_progress("tool_end", f"✅ {tool.name} tamamlandı", {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "tool": tool.name,
                "is_agent_call": is_agent,
                "status": "waiting",
                "output_preview": self._truncate(output_preview, 300),
                "edge_label": self._truncate(output_preview, 80),
                "duration_ms": duration_ms,
            })

        # Firebase logging
        if self.task_logger:
            if isinstance(result, dict):
                output_data = result
            else:
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
        self._send_progress("handoff", f"🔄 {from_agent.name} → {to_agent.name} geçiş yapılıyor", {
            "from_agent_id": self._agent_id_map.get(from_agent.name),
            "from_agent_name": from_agent.name,
            "to_agent_name": to_agent.name,
            "status": "executing",
        })

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

        # --- Workflow: pop agent from stack ---
        agent_id = self._agent_id_map.get(agent.name)
        parent_id: str | None = None
        if self._agent_stack and self._agent_stack[-1] == agent_id:
            self._agent_stack.pop()
            parent_id = self._agent_stack[-1] if self._agent_stack else None

        self._send_progress("agent_end", f"✅ {agent.name} agent tamamlandı", {
            "agent_id": agent_id,
            "parent_agent_id": parent_id,
            "agent_name": agent.name,
            "status": "completed",
            "output_preview": self._truncate(output, 300),
        })

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
