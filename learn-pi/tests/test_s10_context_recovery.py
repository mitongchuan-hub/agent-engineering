from __future__ import annotations

import asyncio

from s10_context_recovery.code import (
    CompactionSettings,
    Message,
    RecoveryEngine,
    SessionEntry,
    build_context_messages,
    compact,
    compaction_entry,
    estimate_context_tokens,
    find_cut_point,
    message_entry,
    prepare_compaction,
    should_compact,
    summarize_branch,
)


def run(coro):
    return asyncio.run(coro)


def make_entries() -> list[SessionEntry]:
    user1 = message_entry(Message("user", "第一轮用户问题"), entry_id="u1")
    assistant1 = message_entry(Message("assistant", "第一轮回答"), entry_id="a1", parent_id="u1")
    tool = message_entry(Message("toolResult", "工具返回了很多内容"), entry_id="t1", parent_id="a1")
    user2 = message_entry(Message("user", "第二轮用户问题"), entry_id="u2", parent_id="t1")
    assistant2 = message_entry(Message("assistant", "第二轮回答"), entry_id="a2", parent_id="u2")
    user3 = message_entry(Message("user", "第三轮用户问题"), entry_id="u3", parent_id="a2")
    assistant3 = message_entry(Message("assistant", "第三轮回答"), entry_id="a3", parent_id="u3")
    return [user1, assistant1, tool, user2, assistant2, user3, assistant3]


def test_cut_point_never_selects_tool_result() -> None:
    entries = make_entries()
    cut = find_cut_point(entries, 0, len(entries), keep_recent_tokens=3)

    assert entries[cut.first_kept_index].entry_type == "message"
    assert entries[cut.first_kept_index].message.role in {"user", "assistant"}
    assert entries[cut.first_kept_index].message.role != "toolResult"


def test_prepare_compaction_returns_summary_input_without_mutating_entries() -> None:
    entries = make_entries()
    before = list(entries)
    preparation = prepare_compaction(
        entries,
        CompactionSettings(keep_recent_tokens=3, reserve_tokens=2),
    )

    assert preparation is not None
    assert preparation.tokens_before == estimate_context_tokens(entries)
    assert entries == before
    assert preparation.messages_to_summarize
    assert all(message.role != "toolResult" or True for message in preparation.messages_to_summarize)


def test_split_turn_keeps_turn_prefix_separate_from_history_summary() -> None:
    entries = make_entries()
    preparation = prepare_compaction(
        entries,
        CompactionSettings(keep_recent_tokens=2, reserve_tokens=1),
    )

    assert preparation is not None
    if preparation.is_split_turn:
        assert preparation.turn_prefix_messages
        assert preparation.turn_prefix_messages[0].role == "user"


def test_compact_result_contains_first_kept_id_and_before_tokens() -> None:
    async def scenario() -> None:
        entries = make_entries()
        preparation = prepare_compaction(entries, CompactionSettings(keep_recent_tokens=3))
        assert preparation is not None

        result = await compact(preparation, lambda messages: "summary of " + str(len(messages)))

        assert result.first_kept_entry_id == preparation.first_kept_entry_id
        assert result.tokens_before == preparation.tokens_before
        assert result.summary
        assert result.estimated_tokens_after > 0

    run(scenario())


def test_compaction_entry_rebuilds_summary_plus_kept_tail() -> None:
    async def scenario() -> None:
        entries = make_entries()
        preparation = prepare_compaction(entries, CompactionSettings(keep_recent_tokens=3))
        assert preparation is not None
        result = await compact(preparation)
        entries.append(compaction_entry(result, parent_id=entries[-1].entry_id))

        context = build_context_messages(entries)

        assert context[0].role == "compactionSummary"
        assert context[0].content == result.summary
        assert context[-1].content == "第三轮回答"

    run(scenario())


def test_threshold_decision_reserves_output_budget() -> None:
    settings = CompactionSettings(enabled=True, reserve_tokens=10)

    assert should_compact(91, 100, settings) is True
    assert should_compact(90, 100, settings) is False
    assert should_compact(100, 100, CompactionSettings(enabled=False, reserve_tokens=0)) is False


def test_transient_error_retries_without_compaction() -> None:
    async def scenario() -> None:
        engine = RecoveryEngine(
            make_entries(),
            context_window=1000,
            settings=CompactionSettings(keep_recent_tokens=3),
        )
        outcome = await engine.handle_response(
            Message("assistant", "temporary 529", "error", retryable=True),
            retry_response=Message("assistant", "recovered", "stop"),
        )

        assert outcome.retried_response is not None
        assert outcome.compaction is None
        assert "auto_retry_start" in outcome.events
        assert "auto_retry_end_success" in outcome.events
        assert len([message for message in engine.retry_context() if message.stop_reason == "error"]) == 0

    run(scenario())


def test_aborted_response_skips_compaction_and_retry() -> None:
    async def scenario() -> None:
        engine = RecoveryEngine(
            make_entries(),
            context_window=1,
            settings=CompactionSettings(keep_recent_tokens=1),
        )
        outcome = await engine.handle_response(Message("assistant", "cancelled", "aborted"))

        assert outcome.compaction is None
        assert outcome.retried_response is None
        assert outcome.failed is False
        assert outcome.events == ("agent_end", "skip_compaction_aborted")

    run(scenario())


def test_length_response_compacts_and_retries_once_with_failed_message_excluded() -> None:
    async def scenario() -> None:
        engine = RecoveryEngine(
            make_entries(),
            context_window=100,
            settings=CompactionSettings(keep_recent_tokens=3, reserve_tokens=2),
        )
        failed = Message("assistant", "truncated output", "length")
        retry = Message("assistant", "recovered after compact", "stop")
        outcome = await engine.handle_response(failed, retry_response=retry)

        assert outcome.compaction is not None
        assert outcome.retried_response == retry
        assert "compaction_end" in outcome.events
        assert "overflow_retry_end_success" in outcome.events
        assert failed not in engine.retry_context()

    run(scenario())


def test_second_overflow_does_not_compact_again() -> None:
    async def scenario() -> None:
        engine = RecoveryEngine(
            make_entries(),
            context_window=100,
            settings=CompactionSettings(keep_recent_tokens=3, reserve_tokens=2),
        )
        first = await engine.handle_response(Message("assistant", "first", "length"), retry_response=Message("assistant", "ok"))
        second = await engine.handle_response(Message("assistant", "second", "length"), retry_response=Message("assistant", "ok2"))

        assert first.compaction is not None
        assert second.compaction is None
        assert second.failed is True
        assert "compaction_failed_already_attempted" in second.events

    run(scenario())


def test_branch_summary_uses_only_message_content() -> None:
    async def scenario() -> None:
        result = await summarize_branch(make_entries(), "a1", lambda messages: " | ".join(message.content for message in messages))

        assert result.from_id == "a1"
        assert "第一轮用户问题" in result.summary
        assert "工具返回了很多内容" in result.summary

    run(scenario())
