"""第 12 章：Session JSONL 存储。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from .models import Message, UserMessage, message_from_dict, message_to_dict


@dataclass(frozen=True, slots=True)
class SessionEntry:
    entry_type: str
    entry_id: str
    parent_id: str | None
    timestamp: str
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.entry_type,
            "id": self.entry_id,
            "parentId": self.parent_id,
            "timestamp": self.timestamp,
            **self.data,
        }


class SessionStore:
    """综合 Agent 使用的最小 append-only Session。"""

    def __init__(
        self,
        cwd: str,
        *,
        path: str | Path | None = None,
        session_id: str | None = None,
        parent_session: str | None = None,
    ) -> None:
        self.cwd = cwd
        self.path = Path(path) if path is not None else None
        self.session_id = session_id or self._new_id()
        self.parent_session = parent_session
        self.entries: list[SessionEntry] = []
        self.leaf_id: str | None = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            header: dict[str, Any] = {
                "type": "session",
                "version": 3,
                "id": self.session_id,
                "timestamp": self._timestamp(),
                "cwd": self.cwd,
            }
            if parent_session is not None:
                header["parentSession"] = parent_session
            self.path.write_text(json.dumps(header) + "\n", encoding="utf-8")

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:8]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, cwd: str, path: str | Path) -> "SessionStore":
        return cls(cwd, path=path)

    @classmethod
    def open(cls, path: str | Path) -> "SessionStore":
        session_path = Path(path)
        lines = session_path.read_text(encoding="utf-8").splitlines()
        header: dict[str, Any] | None = None
        entries: list[SessionEntry] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                # 坏行不应让整个会话无法恢复。
                continue
            if raw.get("type") == "session":
                header = raw
                continue
            if not all(key in raw for key in ("type", "id", "parentId", "timestamp")):
                continue
            data = {
                key: value
                for key, value in raw.items()
                if key not in {"type", "id", "parentId", "timestamp"}
            }
            entries.append(SessionEntry(raw["type"], raw["id"], raw["parentId"], raw["timestamp"], data))
        if header is None:
            raise ValueError(f"无效的 Session 文件: {session_path}")
        store = cls.__new__(cls)
        store.cwd = str(header.get("cwd", ""))
        store.path = session_path
        store.session_id = str(header["id"])
        store.parent_session = header.get("parentSession")
        store.entries = entries
        store.leaf_id = entries[-1].entry_id if entries else None
        return store

    def _append_line(self, entry: SessionEntry) -> None:
        if self.path is not None:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")

    def _append(self, entry_type: str, data: dict[str, Any]) -> str:
        entry = SessionEntry(entry_type, self._new_id(), self.leaf_id, self._timestamp(), data)
        self.entries.append(entry)
        self.leaf_id = entry.entry_id
        self._append_line(entry)
        return entry.entry_id

    def append_message(self, message: Message) -> str:
        return self._append("message", {"message": message_to_dict(message)})

    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int) -> str:
        return self._append(
            "compaction",
            {
                "summary": summary,
                "firstKeptEntryId": first_kept_entry_id,
                "tokensBefore": tokens_before,
            },
        )

    def get_entries(self) -> tuple[SessionEntry, ...]:
        return tuple(self.entries)

    def get_branch(self, leaf_id: str | None = None) -> tuple[SessionEntry, ...]:
        by_id = {entry.entry_id: entry for entry in self.entries}
        current_id = self.leaf_id if leaf_id is None else leaf_id
        branch: list[SessionEntry] = []
        while current_id is not None and current_id in by_id:
            entry = by_id[current_id]
            branch.append(entry)
            current_id = entry.parent_id
        branch.reverse()
        return tuple(branch)

    def branch(self, entry_id: str) -> None:
        if entry_id not in {entry.entry_id for entry in self.entries}:
            raise KeyError(entry_id)
        self.leaf_id = entry_id

    def _context_entries(self, branch: Sequence[SessionEntry]) -> list[SessionEntry]:
        compactions = [entry for entry in branch if entry.entry_type == "compaction"]
        if not compactions:
            return list(branch)
        latest = compactions[-1]
        index = branch.index(latest)
        result = [latest]
        found = False
        for entry in branch[:index]:
            if entry.entry_id == latest.data.get("firstKeptEntryId"):
                found = True
            if found:
                result.append(entry)
        result.extend(branch[index + 1 :])
        return result

    def context_messages(self, excluded_entry_ids: set[str] | None = None) -> tuple[Message, ...]:
        excluded = excluded_entry_ids or set()
        messages: list[Message] = []
        for entry in self._context_entries(self.get_branch()):
            if entry.entry_id in excluded:
                continue
            if entry.entry_type == "message":
                messages.append(message_from_dict(entry.data["message"]))
            elif entry.entry_type == "compaction":
                messages.append(UserMessage(str(entry.data["summary"])))
        return tuple(messages)

    def fork_to(self, target_path: str | Path, target_cwd: str | None = None) -> "SessionStore":
        fork = SessionStore(
            target_cwd or self.cwd,
            path=target_path,
            parent_session=str(self.path) if self.path is not None else None,
        )
        for entry in self.entries:
            fork_entry = SessionEntry(entry.entry_type, entry.entry_id, entry.parent_id, entry.timestamp, dict(entry.data))
            fork.entries.append(fork_entry)
            fork.leaf_id = fork_entry.entry_id
            fork._append_line(fork_entry)
        return fork
