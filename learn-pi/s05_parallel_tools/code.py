#!/usr/bin/env python3
"""第 05 章：并行工具执行和稳定的结果顺序。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
import inspect
from typing import Literal, TypeAlias

ExecutionMode = Literal["parallel", "sequential"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    is_error: bool = False
    terminate: bool = False

ToolExecutor: TypeAlias = Callable[[str, dict], str | ToolResult | Awaitable[str | ToolResult]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    execute: ToolExecutor
    execution_mode: ExecutionMode | None = None


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    terminate: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    type: Literal["tool_execution_start", "tool_execution_end", "message_start", "message_end"]
    call_id: str
    tool_name: str


@dataclass(frozen=True, slots=True)
class ToolBatchResult:
    messages: tuple[ToolResultMessage, ...]
    execution_end_order: tuple[str, ...]
    result_message_order: tuple[str, ...]
    events: tuple[ExecutionEvent, ...]
    terminated: bool


@dataclass(frozen=True, slots=True)
class _PreparedCall:
    call: ToolCall
    tool: Tool


@dataclass(frozen=True, slots=True)
class _Immediate:
    call: ToolCall
    result: ToolResult


async def _call_tool(prepared: _PreparedCall) -> ToolResult:
    try:
        value = prepared.tool.execute(prepared.call.id, prepared.call.arguments)
        if inspect.isawaitable(value):
            value = await value
        if isinstance(value, ToolResult):
            return value
        return ToolResult(str(value))
    except Exception as error:
        return ToolResult(str(error), is_error=True)


def _message(prepared: _PreparedCall, result: ToolResult) -> ToolResultMessage:
    return ToolResultMessage(
        tool_call_id=prepared.call.id,
        tool_name=prepared.call.name,
        content=result.content,
        is_error=result.is_error,
        terminate=result.terminate,
    )


def _error_message(call: ToolCall, content: str) -> ToolResultMessage:
    return ToolResultMessage(call.id, call.name, content, is_error=True)


async def execute_tool_calls(
    calls: Sequence[ToolCall],
    tools: Sequence[Tool],
    *,
    tool_execution: ExecutionMode = "parallel",
    assistant_stop_reason: StopReason = "toolUse",
) -> ToolBatchResult:
    """执行一个 assistant 工具调用批次，并保持 Pi 的顺序语义。"""

    tool_by_name = {tool.name: tool for tool in tools}
    events: list[ExecutionEvent] = []
    execution_end_order: list[str] = []
    immediate: list[_Immediate] = []
    prepared: list[_PreparedCall] = []

    # 在 Pi 中，即使实际执行并行，preflight 仍按源码顺序进行。
    # 这样 lookup/validation 决策会在创建任务前确定。
    if assistant_stop_reason == "length":
        # length 表示整个 assistant 输出可能被截断；所有 tool call 都不能执行。
        for call in calls:
            events.append(ExecutionEvent("tool_execution_start", call.id, call.name))
            immediate.append(
                _Immediate(
                    call,
                    ToolResult(
                        "The tool call was not executed: the response hit the output token limit, "
                        "so its arguments may be truncated.",
                        is_error=True,
                    ),
                )
            )
            events.append(ExecutionEvent("tool_execution_end", call.id, call.name))
            execution_end_order.append(call.id)
    else:
        for call in calls:
            events.append(ExecutionEvent("tool_execution_start", call.id, call.name))
            tool = tool_by_name.get(call.name)
            if tool is None:
                immediate.append(_Immediate(call, ToolResult(f"Tool {call.name} not found", is_error=True)))
                events.append(ExecutionEvent("tool_execution_end", call.id, call.name))
                execution_end_order.append(call.id)
            else:
                prepared.append(_PreparedCall(call, tool))

    force_sequential = any(item.tool.execution_mode == "sequential" for item in prepared)
    # 一个有副作用的 sequential 工具会把整个 batch 拉回顺序执行。
    sequential = tool_execution == "sequential" or force_sequential
    finalized: list[tuple[_PreparedCall, ToolResult]] = []

    if sequential:
        # 顺序模式中，完成事件和结果消息天然都是源码顺序。
        for item in prepared:
            result = await _call_tool(item)
            finalized.append((item, result))
            events.append(ExecutionEvent("tool_execution_end", item.call.id, item.call.name))
            execution_end_order.append(item.call.id)
    else:
        async def run_parallel(item: _PreparedCall) -> tuple[_PreparedCall, ToolResult]:
            result = await _call_tool(item)
            # 这个追加发生在完成时；下面的 gather 仍会按输入/源码顺序返回结果。
            execution_end_order.append(item.call.id)
            events.append(ExecutionEvent("tool_execution_end", item.call.id, item.call.name))
            return item, result

        tasks = [asyncio.create_task(run_parallel(item)) for item in prepared]
        # gather 返回输入顺序；run_parallel 内部的 append 才记录真实完成顺序。
        if tasks:
            finalized = list(await asyncio.gather(*tasks))

    # immediate outcome 已在 preflight 阶段结束；这里按 calls 重建模型看到的源码顺序。
    finalized_by_id: dict[str, tuple[_PreparedCall | None, ToolResult]] = {
        item.call.id: (item, result) for item, result in finalized
    }
    finalized_by_id.update({item.call.id: (None, item.result) for item in immediate})

    messages: list[ToolResultMessage] = []
    for call in calls:
        prepared_item, result = finalized_by_id[call.id]
        if prepared_item is None:
            result_message = _error_message(call, result.content)
        else:
            result_message = _message(prepared_item, result)
        messages.append(result_message)
        events.append(ExecutionEvent("message_start", call.id, call.name))
        events.append(ExecutionEvent("message_end", call.id, call.name))

    terminated = bool(messages) and all(message.terminate for message in messages)
    return ToolBatchResult(
        messages=tuple(messages),
        execution_end_order=tuple(execution_end_order),
        result_message_order=tuple(message.tool_call_id for message in messages),
        events=tuple(events),
        terminated=terminated,
    )


async def demo() -> None:
    async def slow(_id, _args):
        await asyncio.sleep(0.03)
        return "slow done"

    async def fast(_id, _args):
        await asyncio.sleep(0)
        return "fast done"

    result = await execute_tool_calls(
        [ToolCall("call-1", "slow", {}), ToolCall("call-2", "fast", {})],
        [Tool("slow", slow), Tool("fast", fast)],
    )
    print("s05: parallel tools and stable result order\n")
    print(f"execution_end: {list(result.execution_end_order)}")
    print(f"tool_result: {list(result.result_message_order)}")
    print(f"contents: {[message.content for message in result.messages]}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
