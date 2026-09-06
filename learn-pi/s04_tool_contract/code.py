#!/usr/bin/env python3
"""第 04 章：工具查找、参数准备、校验和执行。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import inspect
from typing import Any, Literal, TypeAlias

Schema: TypeAlias = dict[str, Any]
ToolExecutor: TypeAlias = Callable[[str, dict[str, Any]], str | Awaitable[str]]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    terminate: bool = False


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: Schema
    execute: ToolExecutor
    prepare_arguments: Callable[[Any], Any] | None = None


@dataclass(frozen=True, slots=True)
class BeforeToolCallResult:
    block: bool = False
    reason: str | None = None
    terminate: bool = False


@dataclass(frozen=True, slots=True)
class AbortSignal:
    aborted: bool = False


@dataclass(frozen=True, slots=True)
class PreparedToolCall:
    call: ToolCall
    tool: Tool
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    call: ToolCall
    result: ToolResultMessage
    executed: bool


class ToolValidationError(ValueError):
    pass


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _coerce(value: Any, schema: Schema) -> Any:
    """只应用本章需要的少量参数类型转换。"""

    expected = schema.get("type")
    if expected == "integer" and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value
    if expected == "number" and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    if expected == "boolean" and isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _validate(value: Any, schema: Schema, path: str) -> None:
    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_matches_type(value, name) for name in expected):
            raise ToolValidationError(f"{path}: expected one of {expected}, got {_type_name(value)}")
    elif isinstance(expected, str) and not _matches_type(value, expected):
        raise ToolValidationError(f"{path}: expected {expected}, got {_type_name(value)}")

    if isinstance(value, dict) and expected == "object":
        for key in schema.get("required", []):
            if key not in value:
                raise ToolValidationError(f"{path}.{key}: is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ToolValidationError(f"{path}.{unknown[0]}: is not allowed")
        for key, child_schema in properties.items():
            if key in value:
                _validate(value[key], child_schema, f"{path}.{key}")

    if isinstance(value, list) and expected == "array" and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ToolValidationError(f"{path}: must not be shorter than {schema['minLength']} characters")


def validate_arguments(tool: Tool, call: ToolCall) -> dict[str, Any]:
    """复制并校验参数，模拟 Pi 的参数验证边界。"""

    # 先复制模型参数；校验、coerce 或 hook 都不应改写原始 tool call。
    args = deepcopy(dict(call.arguments))
    args = _coerce(args, tool.parameters)
    if not isinstance(args, dict):
        raise ToolValidationError(
            f'Validation failed for tool "{call.name}": root: expected object, got {_type_name(args)}'
        )
    try:
        _validate(args, tool.parameters, "root")
    except ToolValidationError as error:
        raise ToolValidationError(
            f'Validation failed for tool "{call.name}": {error}\nReceived arguments: {dict(call.arguments)!r}'
        ) from error
    return args


def _error(call: ToolCall, message: str, *, terminate: bool = False) -> ToolOutcome:
    return ToolOutcome(
        call,
        ToolResultMessage(call.id, call.name, message, is_error=True, terminate=terminate),
        executed=False,
    )


async def prepare_tool_call(
    tools: list[Tool],
    call: ToolCall,
    *,
    signal: AbortSignal | None = None,
    before_tool_call: Callable[[ToolCall, dict[str, Any]], BeforeToolCallResult | Awaitable[BeforeToolCallResult | None] | None]
    | None = None,
) -> PreparedToolCall | ToolOutcome:
    """执行工具前完成所有准备阶段的决策，但不调用工具本身。"""

    tool = next((candidate for candidate in tools if candidate.name == call.name), None)
    # 找不到工具是 immediate outcome，不进入 execute 阶段。
    if tool is None:
        return _error(call, f"Tool {call.name} not found")

    try:
        raw_arguments: Any = dict(call.arguments)
        # prepare 在 validate 前运行，用于兼容模型输出的 shorthand 形状。
        if tool.prepare_arguments is not None:
            raw_arguments = tool.prepare_arguments(raw_arguments)
        prepared_call = ToolCall(call.id, call.name, raw_arguments)
        validated = validate_arguments(tool, prepared_call)

        if before_tool_call is not None:
            # hook 看到的是 validated args，可做策略判断，也可决定阻止调用。
            decision = before_tool_call(call, validated)
            if inspect.isawaitable(decision):
                decision = await decision
            if signal is not None and signal.aborted:
                return _error(call, "Operation aborted")
            if decision is not None and decision.block:
                return _error(
                    call,
                    decision.reason or "Tool execution was blocked",
                    terminate=decision.terminate,
                )

        if signal is not None and signal.aborted:
            return _error(call, "Operation aborted")
        # beforeToolCall 之后不再重新校验：Pi 允许 hook 修改传给 execute 的已校验参数。
        return PreparedToolCall(call, tool, validated)
    except Exception as error:
        return _error(call, str(error))


async def execute_tool_call(
    tools: list[Tool],
    call: ToolCall,
    *,
    signal: AbortSignal | None = None,
    before_tool_call: Callable[[ToolCall, dict[str, Any]], BeforeToolCallResult | Awaitable[BeforeToolCallResult | None] | None]
    | None = None,
) -> ToolOutcome:
    prepared = await prepare_tool_call(
        tools,
        call,
        signal=signal,
        before_tool_call=before_tool_call,
    )
    if isinstance(prepared, ToolOutcome):
        # 所有 preflight 失败都已封装成模型可见的错误结果。
        return prepared

    try:
        value = prepared.tool.execute(prepared.call.id, prepared.args)
        if inspect.isawaitable(value):
            value = await value
        return ToolOutcome(
            call,
            ToolResultMessage(call.id, call.name, str(value)),
            executed=True,
        )
    except Exception as error:
        # 工具实现抛错也转换成 ToolResult，避免击穿外层 Agent Loop。
        return _error(call, str(error))


async def demo() -> None:
    tool = Tool(
        name="edit",
        description="Turn shorthand edit arguments into an edits list",
        parameters={
            "type": "object",
            "required": ["edits"],
            "properties": {
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["oldText", "newText"],
                        "properties": {"oldText": {"type": "string"}, "newText": {"type": "string"}},
                    },
                }
            },
        },
        prepare_arguments=lambda args: {
            "edits": args.get("edits", [])
            + ([{"oldText": args["oldText"], "newText": args["newText"]}] if "oldText" in args else [])
        },
        execute=lambda _id, args: f"edited {len(args['edits'])} item(s)",
    )
    call = ToolCall("call-1", "edit", {"oldText": "before", "newText": "after"})
    outcome = await execute_tool_call([tool], call)

    print("s04: tool contract and execution pipeline\n")
    print(f"call: {call.name} {dict(call.arguments)}")
    print(f"executed: {outcome.executed}")
    print(f"result: {outcome.result.content}")
    blocked = await execute_tool_call(
        [tool],
        call,
        before_tool_call=lambda _call, _args: BeforeToolCallResult(block=True, reason="policy denied"),
    )
    print(f"blocked: {blocked.result.content} (executed={blocked.executed})")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
