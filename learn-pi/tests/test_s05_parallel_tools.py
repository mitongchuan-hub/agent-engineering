from __future__ import annotations

import asyncio

from s05_parallel_tools.code import Tool, ToolCall, ToolResult, execute_tool_calls


def run(coro):
    return asyncio.run(coro)


def test_parallel_completion_order_differs_from_source_result_order() -> None:
    async def scenario() -> None:
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        overlap = False

        async def slow(_id, _args):
            nonlocal overlap
            first_started.set()
            await second_started.wait()
            overlap = True
            await asyncio.sleep(0.02)
            return "first"

        async def fast(_id, _args):
            second_started.set()
            return "second"

        result = await execute_tool_calls(
            [ToolCall("c1", "slow", {}), ToolCall("c2", "fast", {})],
            [Tool("slow", slow), Tool("fast", fast)],
        )

        assert overlap is True
        assert result.execution_end_order == ("c2", "c1")
        assert result.result_message_order == ("c1", "c2")
        assert [message.content for message in result.messages] == ["first", "second"]

    run(scenario())


def test_sequential_configuration_does_not_overlap_tools() -> None:
    async def scenario() -> None:
        running = 0
        overlap = False

        async def execute(_id, _args):
            nonlocal running, overlap
            running += 1
            overlap = overlap or running > 1
            await asyncio.sleep(0)
            running -= 1
            return "ok"

        result = await execute_tool_calls(
            [ToolCall("c1", "one", {}), ToolCall("c2", "two", {})],
            [Tool("one", execute), Tool("two", execute)],
            tool_execution="sequential",
        )

        assert overlap is False
        assert result.execution_end_order == ("c1", "c2")
        assert result.result_message_order == ("c1", "c2")

    run(scenario())


def test_one_sequential_tool_forces_the_whole_batch_to_be_sequential() -> None:
    async def scenario() -> None:
        running = 0
        overlap = False

        async def execute(_id, _args):
            nonlocal running, overlap
            running += 1
            overlap = overlap or running > 1
            await asyncio.sleep(0)
            running -= 1
            return "ok"

        result = await execute_tool_calls(
            [ToolCall("c1", "parallel", {}), ToolCall("c2", "serial", {})],
            [Tool("parallel", execute), Tool("serial", execute, execution_mode="sequential")],
        )

        assert overlap is False
        assert result.execution_end_order == ("c1", "c2")

    run(scenario())


def test_explicit_parallel_tools_can_overlap() -> None:
    async def scenario() -> None:
        running = 0
        overlap = False
        release = asyncio.Event()

        async def execute(_id, _args):
            nonlocal running, overlap
            running += 1
            overlap = overlap or running > 1
            if running == 2:
                release.set()
            await release.wait()
            running -= 1
            return "ok"

        result = await execute_tool_calls(
            [ToolCall("c1", "one", {}), ToolCall("c2", "two", {})],
            [Tool("one", execute, execution_mode="parallel"), Tool("two", execute, execution_mode="parallel")],
        )

        assert overlap is True
        assert result.result_message_order == ("c1", "c2")

    run(scenario())


def test_length_truncated_batch_never_executes_any_tool() -> None:
    async def scenario() -> None:
        executed: list[str] = []

        async def execute(tool_id, _args):
            executed.append(tool_id)
            return "unsafe"

        result = await execute_tool_calls(
            [ToolCall("c1", "one", {}), ToolCall("c2", "two", {})],
            [Tool("one", execute), Tool("two", execute)],
            assistant_stop_reason="length",
        )

        assert executed == []
        assert all(message.is_error for message in result.messages)
        assert result.execution_end_order == ("c1", "c2")
        assert result.terminated is False

    run(scenario())


def test_tool_exception_is_one_error_result_and_does_not_cancel_other_parallel_call() -> None:
    async def scenario() -> None:
        async def fail(_id, _args):
            raise RuntimeError("boom")

        result = await execute_tool_calls(
            [ToolCall("c1", "fail", {}), ToolCall("c2", "ok", {})],
            [Tool("fail", fail), Tool("ok", lambda _id, _args: "fine")],
        )

        assert result.messages[0].is_error is True
        assert result.messages[0].content == "boom"
        assert result.messages[1].content == "fine"

    run(scenario())


def test_batch_terminates_only_when_every_result_requests_termination() -> None:
    async def scenario() -> None:
        all_stop = await execute_tool_calls(
            [ToolCall("c1", "one", {}), ToolCall("c2", "two", {})],
            [
                Tool("one", lambda _id, _args: ToolResult("one", terminate=True)),
                Tool("two", lambda _id, _args: ToolResult("two", terminate=True)),
            ],
        )
        mixed = await execute_tool_calls(
            [ToolCall("c1", "one", {}), ToolCall("c2", "two", {})],
            [
                Tool("one", lambda _id, _args: ToolResult("one", terminate=True)),
                Tool("two", lambda _id, _args: ToolResult("two", terminate=False)),
            ],
        )

        assert all_stop.terminated is True
        assert mixed.terminated is False

    run(scenario())


def test_missing_tool_is_immediate_but_other_prepared_call_still_runs() -> None:
    async def scenario() -> None:
        result = await execute_tool_calls(
            [ToolCall("c1", "missing", {}), ToolCall("c2", "ok", {})],
            [Tool("ok", lambda _id, _args: "fine")],
        )

        assert result.messages[0].is_error is True
        assert result.messages[1].content == "fine"
        assert result.result_message_order == ("c1", "c2")

    run(scenario())
