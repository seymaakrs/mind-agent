from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.infra.firebase_client import get_document_client


class TaskLogger:
    """
    Task run'lari icin Firebase Firestore loglama.

    Log yapisi:
    businesses/{business_id}/logs/{log_id}
    ├── task: string              # Istek metni
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

    def __init__(self, business_id: str | None = None) -> None:
        self.business_id = business_id
        self.log_id: str | None = None
        self.actions: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self._started_at: datetime | None = None
        self._doc_client = get_document_client("businesses")

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

        log_data = {
            "task": task,
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
        return self.log_id

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


__all__ = ["TaskLogger"]
