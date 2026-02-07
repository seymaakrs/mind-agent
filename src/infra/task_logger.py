from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.infra.firebase_client import get_document_client

logger = logging.getLogger(__name__)


class TaskLogger:
    """
    Task run'lari icin Firebase Firestore loglama.

    Log yapisi:
    businesses/{business_id}/logs/{log_id}
    ├── task: string              # Istek metni
    ├── task_id: string | null    # Admin panelinden gelen task ID
    ├── started_at: timestamp     # Baslangic zamani
    ├── completed_at: timestamp   # Bitis zamani
    ├── status: "running" | "success" | "error"
    ├── actions: [                # Yapilan islemler
    │   {tool, input, output, timestamp}
    │ ]
    ├── outputs: [                # Uretilen dosyalar
    │   {type, path, public_url}
    │ ]
    └── error: string | null      # Hata varsa
    """

    def __init__(self, business_id: str | None = None, task_id: str | None = None) -> None:
        self.business_id = business_id
        self.task_id = task_id
        self.log_id: str | None = None
        self.actions: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self._started_at: datetime | None = None
        self._task: str | None = None  # Store task text for tasks collection
        self._doc_client = get_document_client("businesses")
        self._active_tasks_client = get_document_client("active_tasks")
        self._active_task_id: str | None = None

    def start(self, task: str) -> str | None:
        """
        Yeni bir task log'u baslatir.

        Args:
            task: Kullanicidan gelen istek metni.

        Returns:
            Log ID veya None (business_id yoksa).
        """
        if not self.business_id:
            return None

        self._started_at = datetime.now(timezone.utc)
        self._task = task  # Store for tasks collection

        log_data = {
            "task": task,
            "task_id": self.task_id,
            "started_at": self._started_at.isoformat(),
            "completed_at": None,
            "status": "running",
            "actions": [],
            "outputs": [],
            "error": None,
        }

        result = self._doc_client.add_to_subcollection(
            document_id=self.business_id,
            subcollection_name="logs",
            data=log_data,
        )
        self.log_id = result["documentId"]

        # Create active_tasks entry for production monitoring
        try:
            active_task_data = {
                "business_id": self.business_id,
                "task": task[:500] if len(task) > 500 else task,
                "task_id": self.task_id,
                "log_id": self.log_id,
                "status": "running",
                "started_at": self._started_at.isoformat(),
                "completed_at": None,
                "duration_ms": None,
                "error": None,
                "current_step": None,
                "last_activity_at": None,
                "expires_at": None,
            }
            at_result = self._active_tasks_client.add_document(active_task_data)
            self._active_task_id = at_result["documentId"]
            logger.info(f"[active_tasks] Created: {self._active_task_id}")
        except Exception as e:
            logger.error(f"[active_tasks] Failed to create: {e}", exc_info=True)

        # Update tasks subcollection if task_id provided
        if self.task_id:
            self._doc_client.update_subcollection_doc(
                document_id=self.business_id,
                subcollection_name="tasks",
                subdoc_id=self.task_id,
                data={
                    "status": "running",
                    "logId": self.log_id,
                    "startedAt": self._started_at.isoformat(),
                },
                merge=True,
            )

        return self.log_id

    def update_step(self, tool_name: str) -> None:
        """
        Aktif task'in current_step alanini gunceller (fire-and-forget).

        Bu method logging_hooks'tan asyncio.run_in_executor ile
        cagirilir, boylece agent'i bloklamaz.
        """
        if not self._active_task_id:
            return
        try:
            self._active_tasks_client.set_document(
                self._active_task_id,
                {
                    "current_step": tool_name,
                    "last_activity_at": datetime.now(timezone.utc).isoformat(),
                },
                merge=True,
            )
        except Exception as e:
            logger.warning(f"[active_tasks] Failed to update step: {e}")

    def log_action(
        self,
        tool: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Bir tool call'u loglar.

        Args:
            tool: Tool adi (ornek: "generate_image", "fetch_business").
            input_data: Tool'a verilen input.
            output_data: Tool'dan donen output.
        """
        action = {
            "tool": tool,
            "input": self._sanitize_for_firestore(input_data),
            "output": self._sanitize_for_firestore(output_data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.actions.append(action)

        # Uretilen dosyalari outputs'a ekle
        if output_data and isinstance(output_data, dict):
            if output_data.get("success") and output_data.get("public_url"):
                output_type = "image" if "image" in tool else "video" if "video" in tool else "file"
                self.outputs.append({
                    "type": output_type,
                    "path": output_data.get("path"),
                    "public_url": output_data.get("public_url"),
                })

    def _sanitize_for_firestore(self, data: Any) -> Any:
        """Firestore icin veriyi temizler (nested dict/list derinligini sinirlar)."""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, dict):
            # Cok buyuk verileri truncate et
            result = {}
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 1000:
                    result[k] = v[:1000] + "...[truncated]"
                elif isinstance(v, (dict, list)):
                    result[k] = self._sanitize_for_firestore(v)
                else:
                    result[k] = v
            return result
        if isinstance(data, list):
            return [self._sanitize_for_firestore(item) for item in data[:50]]  # Max 50 item
        return str(data)

    def complete(self, error: str | None = None) -> None:
        """
        Task log'unu tamamlar ve Firebase'e yazar.

        Args:
            error: Hata mesaji (varsa).
        """
        if not self.business_id or not self.log_id:
            return

        completed_at = datetime.now(timezone.utc)
        status = "failed" if error else "completed"

        update_data = {
            "completed_at": completed_at.isoformat(),
            "status": "error" if error else "success",
            "actions": self.actions,
            "outputs": self.outputs,
            "error": error,
        }

        self._doc_client.update_subcollection_doc(
            document_id=self.business_id,
            subcollection_name="logs",
            subdoc_id=self.log_id,
            data=update_data,
            merge=True,
        )

        # Update active_tasks entry
        if self._active_task_id:
            try:
                duration_ms = None
                if self._started_at:
                    duration_ms = int((completed_at - self._started_at).total_seconds() * 1000)

                # expires_at: datetime object (Firestore TTL icin Timestamp type olmali)
                expires_at = completed_at + timedelta(hours=24)

                self._active_tasks_client.set_document(
                    self._active_task_id,
                    {
                        "status": "success" if not error else "failed",
                        "completed_at": completed_at.isoformat(),
                        "duration_ms": duration_ms,
                        "error": error,
                        "current_step": None,
                        "expires_at": expires_at,
                    },
                    merge=True,
                )
            except Exception as e:
                logger.error(f"[active_tasks] Failed to complete: {e}", exc_info=True)

        # Update tasks subcollection if task_id provided
        if self.task_id:
            task_update: dict[str, Any] = {
                "status": status,
                "completedAt": completed_at.isoformat(),
            }
            if error:
                task_update["error"] = error
            else:
                # Get final output from last action if available
                if self.actions:
                    last_output = self.actions[-1].get("output", {})
                    if isinstance(last_output, dict):
                        task_update["result"] = last_output.get("message", "Task completed")
                    else:
                        task_update["result"] = "Task completed"
                else:
                    task_update["result"] = "Task completed"

            self._doc_client.update_subcollection_doc(
                document_id=self.business_id,
                subcollection_name="tasks",
                subdoc_id=self.task_id,
                data=task_update,
                merge=True,
            )


__all__ = ["TaskLogger"]
