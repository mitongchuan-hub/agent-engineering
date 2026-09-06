"""第 12 章：工具注册和批处理。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
import inspect
from typing import Any, Literal, TypeAlias

from .models import ToolCall, ToolResultMessage

ToolExecutor: TypeAlias = Callable[[dict[str, Any]], str | Awaitable[str]]
ExecutionMode = Literal["parallel", "sequential"]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    execute: ToolExecutor
    execution_mode: ExecutionMode | None = None


@dataclass(frozen=True, slots=True)
class ToolBatch:
    results: tuple[ToolResultMessage, ...]
    execution_end_order: tuple[str, ...]
    terminated: bool


class ToolRegistry:
    """维护扩展/内置工具，并把一个 assistant batch 转为结果消息。"""

    def __init__(self) -> None:
        self._tools: list[ToolDefinition] = []

    def register(self, tool: ToolDefinition) -> None:
        if any(existing.name == tool.name for existing in self._tools):
            raise ValueError(f"工具已注册: {tool.name}")
        self._tools.append(tool)

    def names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self._tools)

    def get(self, name: str) -> ToolDefinition | None:
        return next((tool for tool in self._tools if tool.name == name), None)

    async def _execute_one(self, call: ToolCall) -> ToolResultMessage:
        tool = self.get(call.name)
        if tool is None:
            return ToolResultMessage(call.id, call.name, f"Tool {call.name} not found", True)
        try:
            value = tool.execute(call.arguments)
            if inspect.isawaitable(value):
                value = await value
            return ToolResultMessage(call.id, call.name, str(value))
        except Exception as error:
            return ToolResultMessage(call.id, call.name, str(error), True)

    async def execute_batch(
        self,
        calls: Sequence[ToolCall],
        *,
        mode: ExecutionMode = "parallel",
        stop_reason: Literal["toolUse", "length"] = "toolUse",
    ) -> ToolBatch:
        """并发执行但按 calls 源码顺序返回结果。"""

        if stop_reason == "length":
            results = tuple(
                ToolResultMessage(
                    call.id,
                    call.name,
                    "Tool call was not executed because the assistant response was truncated.",
                    True,
                )
                for call in calls
            )
            return ToolBatch(results, tuple(call.id for call in calls), False)

        sequential = mode == "sequential" or any(
            (self.get(call.name) is not None and self.get(call.name).execution_mode == "sequential")
            for call in calls
        )
        end_order: list[str] = []

        async def run(call: ToolCall) -> ToolResultMessage:
            result = await self._execute_one(call)
            end_order.append(call.id)
            return result

        if sequential:
            results = tuple(await run(call) for call in calls)
        else:
            # gather 的返回顺序稳定，run 内的 end_order 记录真实完成顺序。
            results = tuple(await asyncio.gather(*(run(call) for call in calls)))
        return ToolBatch(results, tuple(end_order), False)
