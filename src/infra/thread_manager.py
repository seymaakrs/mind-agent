from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.infra.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

# Firestore document size limit is 1 MB.
# Each message item is ~200-500 bytes on average; 100 items ≈ 50 KB — well within limits.
_MAX_HISTORY_ITEMS = 100


def generate_thread_id() -> str:
    """Return a new unique thread ID (32-char lowercase hex)."""
    return uuid.uuid4().hex


class ThreadManager:
    """Load and save multi-turn conversation history for a business thread.

    Firestore path: businesses/{business_id}/threads/{thread_id}

    Document schema:
        {
            "messages":    [...],         # full result.to_input_list() output
            "created_at":  "ISO-8601",
            "updated_at":  "ISO-8601",
            "turn_count":  int,           # number of user turns (for admin panel)
        }
    """

    def _ref(self, business_id: str, thread_id: str):
        db = get_firestore_client()
        return (
            db.collection("businesses")
            .document(business_id)
            .collection("threads")
            .document(thread_id)
        )

    def load(self, business_id: str, thread_id: str) -> list[dict[str, Any]]:
        """Return stored message list, or [] if the thread does not exist yet.

        Never raises — Firestore failures fall back to empty history so the
        caller continues in single-turn mode rather than crashing.

        Args:
            business_id: Firestore businesses document ID.
            thread_id:   Thread document ID within the threads subcollection.

        Returns:
            List of TResponseInputItem dicts (may be empty).
        """
        try:
            doc = self._ref(business_id, thread_id).get()
            if not doc.exists:
                logger.debug(
                    "[ThreadManager] thread not found — starting fresh "
                    "(business=%s thread=%s)", business_id, thread_id,
                )
                return []

            data = doc.to_dict() or {}
            messages = data.get("messages", [])

            if not isinstance(messages, list):
                logger.warning(
                    "[ThreadManager] messages field is not a list, resetting "
                    "(business=%s thread=%s)", business_id, thread_id,
                )
                return []

            return messages

        except Exception:
            logger.exception(
                "[ThreadManager] load failed, falling back to empty history "
                "(business=%s thread=%s)", business_id, thread_id,
            )
            return []

    def save(
        self,
        business_id: str,
        thread_id: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """Persist conversation history to Firestore.

        Silently trims to the last _MAX_HISTORY_ITEMS items to stay within
        Firestore document size limits. Never raises — a save failure must not
        affect a run that has already returned its result to the client.

        Args:
            business_id: Firestore businesses document ID.
            thread_id:   Thread document ID.
            messages:    Full message list from result.to_input_list().
        """
        if not messages:
            return

        if len(messages) > _MAX_HISTORY_ITEMS:
            logger.warning(
                "[ThreadManager] trimming history from %d to %d items "
                "(business=%s thread=%s)",
                len(messages), _MAX_HISTORY_ITEMS, business_id, thread_id,
            )
            messages = messages[-_MAX_HISTORY_ITEMS:]

        now = datetime.now(timezone.utc).isoformat()
        turn_count = sum(
            1 for m in messages
            if isinstance(m, dict) and m.get("role") == "user"
        )

        try:
            ref = self._ref(business_id, thread_id)
            existing = ref.get()

            # Preserve created_at from the first save
            created_at = now
            if existing.exists:
                data = existing.to_dict() or {}
                created_at = data.get("created_at", now)

            # merge=False: replace the whole document atomically.
            # merge=True would keep stale keys and Firestore array-union
            # semantics would break message ordering.
            ref.set(
                {
                    "messages": messages,
                    "created_at": created_at,
                    "updated_at": now,
                    "turn_count": turn_count,
                },
                merge=False,
            )

        except Exception:
            logger.exception(
                "[ThreadManager] save failed — conversation history NOT persisted "
                "(business=%s thread=%s)", business_id, thread_id,
            )
            # Do not re-raise: the run result is already on its way to the client.


__all__ = ["ThreadManager", "generate_thread_id"]
