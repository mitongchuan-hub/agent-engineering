#!/usr/bin/env python3
"""第 09 章：Pi v3 JSONL Session、活动分支和 fork。"""

from __future__ import annotations

from collections.abc import Iterable
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any

CURRENT_SESSION_VERSION = 3


@dataclass(frozen=True, slots=True)
class SessionHeader:
    session_id: str
    cwd: str
    timestamp: str
    parent_session: str | None = None
    version: int = CURRENT_SESSION_VERSION

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "type": "session",
            "version": self.version,
            "id": self.session_id,
            "timestamp": self.timestamp,
            "cwd": self.cwd,
        }
        if self.parent_session is not None:
            value["parentSession"] = self.parent_session
        return value


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


@dataclass(slots=True)
class TreeNode:
    entry: SessionEntry
    children: list["TreeNode"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SessionContext:
    entries: tuple[SessionEntry, ...]
    messages: tuple[dict[str, Any], ...]


class SessionManager:
    """只负责 Session 记忆，不负责模型请求或 Agent Loop。"""

    def __init__(
        self,
        cwd: str,
        *,
        path: Path | None = None,
        session_id: str | None = None,
        parent_session: str | None = None,
        entries: Iterable[SessionEntry] = (),
        persist: bool = False,
    ) -> None:
        self.cwd = cwd
        self.path = path
        self.persist = persist and path is not None
        self.header = SessionHeader(
            session_id=session_id or self._new_id(),
            cwd=cwd,
            timestamp=self._timestamp(),
            parent_session=parent_session,
        )
        self.entries: list[SessionEntry] = list(entries)
        self._by_id = {entry.entry_id: entry for entry in self.entries}
        self.leaf_id: str | None = self.entries[-1].entry_id if self.entries else None
        if self.persist and self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.header.as_dict()) + "\n", encoding="utf-8")
            for entry in self.entries:
                self._append_line(entry)

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:8]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def in_memory(cls, cwd: str = "demo-project") -> "SessionManager":
        return cls(cwd)

    @classmethod
    def create(cls, cwd: str, path: str | Path) -> "SessionManager":
        return cls(cwd, path=Path(path), persist=True)

    @classmethod
    def open(cls, path: str | Path) -> "SessionManager":
        session_path = Path(path)
        entries: list[SessionEntry] = []
        header_data: dict[str, Any] | None = None
        if session_path.exists():
            for line in session_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    # 与 Pi 一样跳过损坏行，尽量恢复其余历史。
                    continue
                if raw.get("type") == "session":
                    header_data = raw
                    continue
                if not all(key in raw for key in ("type", "id", "parentId", "timestamp")):
                    continue
                data = {
                    key: value
                    for key, value in raw.items()
                    if key not in {"type", "id", "parentId", "timestamp"}
                }
                entries.append(
                    SessionEntry(raw["type"], raw["id"], raw["parentId"], raw["timestamp"], data)
                )
        if header_data is None:
            raise ValueError(f"不是有效的 Pi Session 文件: {session_path}")
        manager = cls.__new__(cls)
        manager.cwd = str(header_data.get("cwd", ""))
        manager.path = session_path
        manager.persist = True
        manager.header = SessionHeader(
            session_id=header_data["id"],
            cwd=manager.cwd,
            timestamp=header_data["timestamp"],
            parent_session=header_data.get("parentSession"),
            version=header_data.get("version", 1),
        )
        manager.entries = entries
        manager._by_id = {entry.entry_id: entry for entry in entries}
        manager.leaf_id = entries[-1].entry_id if entries else None
        return manager

    def _append_line(self, entry: SessionEntry) -> None:
        if self.path is not None:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(entry.as_dict(), ensure_ascii=False) + "\n")

    def _append_entry(self, entry_type: str, data: dict[str, Any]) -> str:
        # leaf 是唯一的写入游标；新 entry 永远挂在当前 leaf 下。
        entry = SessionEntry(entry_type, self._new_id(), self.leaf_id, self._timestamp(), data)
        self.entries.append(entry)
        self._by_id[entry.entry_id] = entry
        self.leaf_id = entry.entry_id
        self._append_line(entry)
        return entry.entry_id

    def append_message(self, role: str, content: str, **extra: Any) -> str:
        return self._append_entry("message", {"message": {"role": role, "content": content, **extra}})

    def append_custom_entry(self, custom_type: str, data: Any) -> str:
        # custom entry 用来保存扩展状态，本身不进入 LLM context。
        return self._append_entry("custom", {"customType": custom_type, "data": data})

    def append_label(self, label: str) -> str:
        return self._append_entry("label", {"label": label})

    def append_branch_summary(self, summary: str, from_id: str | None = None) -> str:
        return self._append_entry(
            "branch_summary",
            {"fromId": from_id or self.leaf_id or "root", "summary": summary},
        )

    def get_entry(self, entry_id: str) -> SessionEntry | None:
        return self._by_id.get(entry_id)

    def get_entries(self) -> tuple[SessionEntry, ...]:
        return tuple(self.entries)

    def get_children(self, parent_id: str) -> tuple[SessionEntry, ...]:
        return tuple(entry for entry in self.entries if entry.parent_id == parent_id)

    def get_branch(self, leaf_id: str | None = None) -> tuple[SessionEntry, ...]:
        current_id = self.leaf_id if leaf_id is None else leaf_id
        path: list[SessionEntry] = []
        while current_id is not None:
            entry = self._by_id.get(current_id)
            if entry is None:
                break
            path.append(entry)
            current_id = entry.parent_id
        path.reverse()
        return tuple(path)

    def build_context(self, leaf_id: str | None = None) -> SessionContext:
        branch = self.get_branch(leaf_id)
        messages: list[dict[str, Any]] = []
        for entry in branch:
            if entry.entry_type == "message":
                messages.append(entry.data["message"])
            elif entry.entry_type == "branch_summary":
                messages.append({"role": "user", "content": f"[branch summary]\n{entry.data['summary']}"})
            # custom/label/model metadata 只保留在 Session，不直接发给模型。
        return SessionContext(branch, tuple(messages))

    def branch(self, from_id: str) -> None:
        if from_id not in self._by_id:
            raise KeyError(f"Entry {from_id} not found")
        # 不删除任何 entry，只移动 leaf；下一次 append 会创建兄弟分支。
        self.leaf_id = from_id

    def get_tree(self) -> tuple[TreeNode, ...]:
        nodes = {entry.entry_id: TreeNode(entry) for entry in self.entries}
        roots: list[TreeNode] = []
        for entry in self.entries:
            node = nodes[entry.entry_id]
            if entry.parent_id is None or entry.parent_id == entry.entry_id:
                roots.append(node)
            elif entry.parent_id in nodes:
                nodes[entry.parent_id].children.append(node)
            else:
                # 断链 entry 仍然可见，作为孤立根节点返回。
                roots.append(node)
        return tuple(roots)

    def fork_to(self, target_path: str | Path, target_cwd: str | None = None) -> "SessionManager":
        """复制完整 entry 历史到新文件，header 使用新的 session id。"""

        target = Path(target_path)
        forked = SessionManager(
            target_cwd or self.cwd,
            path=target,
            session_id=self._new_id(),
            parent_session=str(self.path) if self.path is not None else None,
            entries=self.entries,
            persist=True,
        )
        forked.leaf_id = self.leaf_id
        return forked


def _flatten_tree(nodes: Sequence[TreeNode]) -> list[str]:
    result: list[str] = []
    for node in nodes:
        result.append(node.entry.entry_id)
        result.extend(_flatten_tree(node.children))
    return result


async def demo() -> None:
    session = SessionManager.in_memory("demo")
    root = session.append_message("user", "实现读取功能")
    assistant = session.append_message("assistant", "我先查看项目")
    session.append_message("user", "补充：关注测试")
    session.branch(assistant)
    branch_user = session.append_message("user", "改走文档方案")
    session.append_message("assistant", "好的，我会先看文档")

    print("s09: JSONL Session and tree memory\n")
    print(f"root: {root}, branch point: {assistant}, branch leaf: {branch_user}")
    print(f"active branch: {[entry.entry_id for entry in session.get_branch()]}")
    print(f"context: {[message['content'] for message in session.build_context().messages]}")
    print(f"tree entries: {_flatten_tree(session.get_tree())}")
    print(f"all entries retained: {len(session.get_entries())}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
