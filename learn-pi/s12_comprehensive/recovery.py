"""第 12 章：综合 Agent 的恢复适配器。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .session import SessionEntry, SessionStore


@dataclass(frozen=True, slots=True)
class CompactionRecord:
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    tokens_after: int


@dataclass(slots=True)
class RecoveryPolicy:
    """只提供综合章需要的离线压缩策略。"""

    max_context_messages: int = 8
    keep_recent_messages: int = 4
    overflow_attempted: bool = False

    @staticmethod
    def _token_count(text: str) -> int:
        return max(1, math.ceil(len(text) / 4))

    def _message_entries(
        self,
        session: SessionStore,
        excluded_entry_ids: set[str],
    ) -> list[SessionEntry]:
        return [
            entry
            for entry in session.get_entries()
            if entry.entry_type == "message"
            and entry.entry_id not in excluded_entry_ids
            and entry.data.get("message", {}).get("role") in {"user", "assistant", "toolResult"}
        ]

    def compact_if_needed(
        self,
        session: SessionStore,
        *,
        excluded_entry_ids: set[str] | None = None,
        force: bool = False,
    ) -> CompactionRecord | None:
        """上下文超过阈值时追加 summary；overflow 可显式强制尝试。"""

        excluded = excluded_entry_ids or set()
        candidates = self._message_entries(session, excluded)
        if not force and len(candidates) <= self.max_context_messages:
            return None
        if len(candidates) <= 1:
            return None
        keep_count = max(1, min(self.keep_recent_messages, len(candidates) - 1))
        first_kept = candidates[-keep_count]
        summarized = candidates[:-keep_count]
        summary = "\n".join(
            f"- {entry.data['message']['role']}: {entry.data['message'].get('content', '')}"
            for entry in summarized
        )
        tokens_before = sum(
            self._token_count(entry.data["message"].get("content", "")) for entry in candidates
        )
        session.append_compaction(summary, first_kept.entry_id, tokens_before)
        return CompactionRecord(
            summary=summary,
            first_kept_entry_id=first_kept.entry_id,
            tokens_before=tokens_before,
            tokens_after=self._token_count(summary),
        )

    def handle_length_stop(
        self,
        session: SessionStore,
        failed_entry_id: str,
    ) -> CompactionRecord | None:
        """length 只允许一次 compact-and-retry。"""

        if self.overflow_attempted:
            return None
        self.overflow_attempted = True
        return self.compact_if_needed(
            session,
            excluded_entry_ids={failed_entry_id},
            force=True,
        )
