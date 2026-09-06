#!/usr/bin/env python3
"""第 10 章：上下文压缩、重试和恢复。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Literal, TypeAlias
import uuid


MessageRole = Literal[
    "user",
    "assistant",
    "toolResult",
    "compactionSummary",
    "branchSummary",
]
StopReason = Literal["stop", "error", "aborted", "length"]


@dataclass(frozen=True, slots=True)
class Message:
    role: MessageRole
    content: str
    stop_reason: StopReason | None = None
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class SessionEntry:
    entry_type: Literal["message", "compaction", "branch_summary"]
    entry_id: str
    parent_id: str | None
    timestamp: str
    message: Message | None = None
    summary: str | None = None
    first_kept_entry_id: str | None = None
    tokens_before: int | None = None
    from_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompactionSettings:
    enabled: bool = True
    reserve_tokens: int = 16
    keep_recent_tokens: int = 24


@dataclass(frozen=True, slots=True)
class CutPoint:
    first_kept_index: int
    turn_start_index: int
    is_split_turn: bool


@dataclass(frozen=True, slots=True)
class CompactionPreparation:
    first_kept_entry_id: str
    messages_to_summarize: tuple[Message, ...]
    turn_prefix_messages: tuple[Message, ...]
    is_split_turn: bool
    tokens_before: int
    previous_summary: str | None


@dataclass(frozen=True, slots=True)
class CompactionResult:
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    estimated_tokens_after: int


@dataclass(frozen=True, slots=True)
class BranchSummaryResult:
    from_id: str
    summary: str


@dataclass(frozen=True, slots=True)
class RecoveryOutcome:
    response: Message
    retried_response: Message | None
    compaction: CompactionResult | None
    events: tuple[str, ...]
    failed: bool


SummaryFn: TypeAlias = Callable[[Sequence[Message]], str | Awaitable[str]]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def message_entry(message: Message, *, entry_id: str | None = None, parent_id: str | None = None) -> SessionEntry:
    return SessionEntry("message", entry_id or _new_id(), parent_id, _timestamp(), message=message)


def compaction_entry(result: CompactionResult, *, parent_id: str | None = None) -> SessionEntry:
    return SessionEntry(
        "compaction",
        _new_id(),
        parent_id,
        _timestamp(),
        summary=result.summary,
        first_kept_entry_id=result.first_kept_entry_id,
        tokens_before=result.tokens_before,
    )


def estimate_tokens(message: Message) -> int:
    """用 Pi 的 chars/4 思路估算消息成本。"""

    return max(1, math.ceil(len(message.content) / 4))


def _context_entries(entries: Sequence[SessionEntry]) -> list[SessionEntry]:
    """将最新 compaction 投影成 summary + 保留尾部。"""

    latest_index = -1
    for index, entry in enumerate(entries):
        if entry.entry_type == "compaction":
            latest_index = index
    if latest_index < 0:
        return list(entries)

    latest = entries[latest_index]
    result = [latest]
    found_first_kept = False
    for entry in entries[:latest_index]:
        if entry.entry_id == latest.first_kept_entry_id:
            found_first_kept = True
        if found_first_kept:
            result.append(entry)
    result.extend(entries[latest_index + 1 :])
    return result


def build_context_messages(
    entries: Sequence[SessionEntry],
    *,
    excluded_entry_ids: set[str] | None = None,
) -> list[Message]:
    excluded = excluded_entry_ids or set()
    messages: list[Message] = []
    for entry in _context_entries(entries):
        if entry.entry_id in excluded:
            continue
        if entry.entry_type == "message" and entry.message is not None:
            messages.append(entry.message)
        elif entry.entry_type == "compaction" and entry.summary is not None:
            messages.append(Message("compactionSummary", entry.summary))
        elif entry.entry_type == "branch_summary" and entry.summary is not None:
            messages.append(Message("branchSummary", entry.summary))
    return messages


def estimate_context_tokens(entries: Sequence[SessionEntry]) -> int:
    return sum(estimate_tokens(message) for message in build_context_messages(entries))


def should_compact(context_tokens: int, context_window: int, settings: CompactionSettings) -> bool:
    return settings.enabled and context_tokens > context_window - settings.reserve_tokens


def _message_at(entries: Sequence[SessionEntry], index: int) -> Message | None:
    entry = entries[index]
    return entry.message if entry.entry_type == "message" else None


def _is_cut_point(message: Message | None) -> bool:
    # toolResult 必须跟在对应 tool call 后面，不能把它单独切掉。
    return message is not None and message.role in {"user", "assistant"}


def _is_turn_start(message: Message | None) -> bool:
    return message is not None and message.role == "user"


def find_cut_point(
    entries: Sequence[SessionEntry],
    start_index: int,
    end_index: int,
    keep_recent_tokens: int,
) -> CutPoint:
    """从新到旧累计 token，并选择不落在 toolResult 上的切点。"""

    cut_points = [
        index
        for index in range(start_index, end_index)
        if _is_cut_point(_message_at(entries, index))
    ]
    if not cut_points:
        return CutPoint(start_index, -1, False)

    accumulated = 0
    cut_index = cut_points[0]
    for index in range(end_index - 1, start_index - 1, -1):
        message = _message_at(entries, index)
        if message is None:
            continue
        accumulated += estimate_tokens(message)
        if accumulated >= keep_recent_tokens:
            cut_index = next((candidate for candidate in cut_points if candidate >= index), cut_points[-1])
            break

    cut_message = _message_at(entries, cut_index)
    if _is_turn_start(cut_message):
        return CutPoint(cut_index, -1, False)

    turn_start = -1
    for index in range(cut_index, start_index - 1, -1):
        if _is_turn_start(_message_at(entries, index)):
            turn_start = index
            break
    return CutPoint(cut_index, turn_start, turn_start != -1)


def prepare_compaction(
    entries: Sequence[SessionEntry],
    settings: CompactionSettings,
) -> CompactionPreparation | None:
    """计算压缩输入，不调用 summarizer，也不修改 Session。"""

    if not entries or entries[-1].entry_type == "compaction":
        return None

    previous_summary: str | None = None
    boundary_start = 0
    previous_index = next(
        (index for index in range(len(entries) - 1, -1, -1) if entries[index].entry_type == "compaction"),
        -1,
    )
    if previous_index >= 0:
        previous = entries[previous_index]
        previous_summary = previous.summary
        kept_index = next(
            (index for index, entry in enumerate(entries) if entry.entry_id == previous.first_kept_entry_id),
            -1,
        )
        boundary_start = kept_index if kept_index >= 0 else previous_index + 1

    cut = find_cut_point(entries, boundary_start, len(entries), settings.keep_recent_tokens)
    first_kept = entries[cut.first_kept_index]
    if not first_kept.entry_id:
        return None

    history_end = cut.turn_start_index if cut.is_split_turn else cut.first_kept_index
    summarized = tuple(
        message
        for index in range(boundary_start, history_end)
        if (message := _message_at(entries, index)) is not None
    )
    turn_prefix = tuple(
        message
        for index in range(cut.turn_start_index, cut.first_kept_index)
        if (message := _message_at(entries, index)) is not None
    ) if cut.is_split_turn else ()

    if not summarized and not turn_prefix:
        return None
    return CompactionPreparation(
        first_kept_entry_id=first_kept.entry_id,
        messages_to_summarize=summarized,
        turn_prefix_messages=turn_prefix,
        is_split_turn=cut.is_split_turn,
        tokens_before=estimate_context_tokens(entries),
        previous_summary=previous_summary,
    )


async def _summary(summary_fn: SummaryFn, messages: Sequence[Message]) -> str:
    value = summary_fn(messages)
    if hasattr(value, "__await__"):
        return await value  # type: ignore[misc]
    return value  # type: ignore[return-value]


async def compact(
    preparation: CompactionPreparation,
    summary_fn: SummaryFn | None = None,
) -> CompactionResult:
    """根据 preparation 生成摘要；Session entry 的 id/parent 由调用方补齐。"""

    summarizer = summary_fn or default_summary
    history = await _summary(summarizer, preparation.messages_to_summarize)
    if preparation.previous_summary:
        history = preparation.previous_summary + "\n\n" + history
    summary = history
    if preparation.is_split_turn:
        prefix = await _summary(summarizer, preparation.turn_prefix_messages)
        summary = f"{history}\n\n---\n\nTurn Context (split turn):\n{prefix}"

    # 结果上下文只保留摘要、首个 kept entry 及其后的路径。
    estimated_after = max(1, math.ceil(len(summary) / 4))
    return CompactionResult(
        summary=summary,
        first_kept_entry_id=preparation.first_kept_entry_id,
        tokens_before=preparation.tokens_before,
        estimated_tokens_after=estimated_after,
    )


def default_summary(messages: Sequence[Message]) -> str:
    if not messages:
        return "(no prior history)"
    return "\n".join(f"- {message.role}: {message.content}" for message in messages)


async def summarize_branch(
    entries: Sequence[SessionEntry],
    from_id: str,
    summary_fn: SummaryFn | None = None,
) -> BranchSummaryResult:
    """对离开的分支生成摘要；摘要本身由 Session 层决定是否落盘。"""

    messages = [entry.message for entry in entries if entry.entry_type == "message" and entry.message is not None]
    summary = await _summary(summary_fn or default_summary, messages)
    return BranchSummaryResult(from_id, summary)


class RecoveryEngine:
    """将一次 assistant 响应接入压缩/重试恢复流程。"""

    def __init__(
        self,
        entries: Sequence[SessionEntry],
        *,
        context_window: int,
        settings: CompactionSettings,
        summary_fn: SummaryFn | None = None,
    ) -> None:
        self.entries = list(entries)
        self.context_window = context_window
        self.settings = settings
        self.summary_fn = summary_fn or default_summary
        self.overflow_recovery_attempted = False
        self.excluded_from_retry: set[str] = set()

    async def handle_response(
        self,
        response: Message,
        *,
        retry_response: Message | None = None,
    ) -> RecoveryOutcome:
        response_entry = message_entry(response, parent_id=self.entries[-1].entry_id if self.entries else None)
        self.entries.append(response_entry)
        events = ["agent_end"]

        if response.stop_reason == "aborted":
            # 用户取消不是上下文溢出，不应自动压缩或重试。
            events.append("skip_compaction_aborted")
            return RecoveryOutcome(response, None, None, tuple(events), False)

        if response.stop_reason == "error" and response.retryable and retry_response is not None:
            events.append("auto_retry_start")
            self.excluded_from_retry.add(response_entry.entry_id)
            retry_entry = message_entry(retry_response, parent_id=response_entry.entry_id)
            self.entries.append(retry_entry)
            events.extend(["auto_retry_end_success"])
            return RecoveryOutcome(response, retry_response, None, tuple(events), False)

        context_tokens = estimate_context_tokens(self.entries)
        overflow = response.stop_reason == "length" or (
            response.stop_reason == "error" and "context" in response.content.lower()
        )
        threshold = should_compact(context_tokens, self.context_window, self.settings)
        if not overflow and not threshold:
            events.append("settled_without_recovery")
            return RecoveryOutcome(response, None, None, tuple(events), False)

        if overflow and self.overflow_recovery_attempted:
            events.append("compaction_failed_already_attempted")
            return RecoveryOutcome(response, None, None, tuple(events), True)
        if overflow:
            self.overflow_recovery_attempted = True

        preparation = prepare_compaction(self.entries, self.settings)
        if preparation is None:
            events.append("compaction_skipped_no_cut_point")
            return RecoveryOutcome(response, None, None, tuple(events), overflow)

        events.append("compaction_start_overflow" if overflow else "compaction_start_threshold")
        result = await compact(preparation, self.summary_fn)
        self.entries.append(compaction_entry(result, parent_id=self.entries[-1].entry_id))
        events.append("compaction_end")

        if overflow and retry_response is not None:
            self.excluded_from_retry.add(response_entry.entry_id)
            events.append("overflow_retry_start")
            retry_entry = message_entry(retry_response, parent_id=self.entries[-1].entry_id)
            self.entries.append(retry_entry)
            events.append("overflow_retry_end_success")
            return RecoveryOutcome(response, retry_response, result, tuple(events), False)

        return RecoveryOutcome(response, None, result, tuple(events), False)

    def retry_context(self) -> tuple[Message, ...]:
        return tuple(build_context_messages(self.entries, excluded_entry_ids=self.excluded_from_retry))


async def demo() -> None:
    entries = [
        message_entry(Message("user", "实现一个功能"), entry_id="u1"),
        message_entry(Message("assistant", "先查看文件"), entry_id="a1", parent_id="u1"),
        message_entry(Message("toolResult", "文件内容"), entry_id="t1", parent_id="a1"),
        message_entry(Message("user", "继续实现"), entry_id="u2", parent_id="t1"),
        message_entry(Message("assistant", "输出达到上限", "length"), entry_id="a2", parent_id="u2"),
    ]
    engine = RecoveryEngine(
        entries,
        context_window=60,
        settings=CompactionSettings(keep_recent_tokens=8, reserve_tokens=8),
    )
    outcome = await engine.handle_response(
        Message("assistant", "输出达到上限", "length"),
        retry_response=Message("assistant", "已根据压缩后的上下文继续", "stop"),
    )

    print("s10: context recovery\n")
    print(f"events: {list(outcome.events)}")
    print(f"context after recovery: {[message.content for message in engine.retry_context()]}")
    print(f"tokens before: {outcome.compaction.tokens_before if outcome.compaction else 'n/a'}")
    print(f"entries retained: {len(engine.entries)}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
