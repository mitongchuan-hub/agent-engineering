#!/usr/bin/env python3
"""第 01 章：最小的、以 Pi 源码为依据的 Agent Loop。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import inspect
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol, Sequence, TypeAlias, cast

StopReason = Literal["stop", "toolUse", "length", "error", "aborted"]


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    type: Literal["text"] = field(default="text", init=False)


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]
    type: Literal["toolCall"] = field(default="toolCall", init=False)


AssistantBlock: TypeAlias = TextBlock | ToolCall


@dataclass(frozen=True, slots=True)
class UserMessage:
    content: str
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    content: tuple[AssistantBlock, ...]
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    role: Literal["assistant"] = field(default="assistant", init=False)

    @property
    def tool_calls(self) -> tuple[ToolCall, ...]:
        return tuple(block for block in self.content if isinstance(block, ToolCall))


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    role: Literal["toolResult"] = field(default="toolResult", init=False)


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage

# Provider 只看统一的 Message；工具和循环的内部差异在边界处被隐藏。
ToolValue: TypeAlias = str | Awaitable[str]
ToolExecutor: TypeAlias = Callable[[str, Mapping[str, Any]], ToolValue]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    execute: ToolExecutor


@dataclass(slots=True)
class AgentContext:
    system_prompt: str
    messages: list[Message]
    tools: list[Tool]


@dataclass(frozen=True, slots=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[Message, ...]
    tool_names: tuple[str, ...]


class Provider(Protocol):
    async def complete(self, request: ModelRequest) -> AssistantMessage:
        """返回一条完整的 assistant 消息。"""


@dataclass(slots=True)
class ScriptedProvider:
    """确定性的 Provider 桩，同时记录每次模型可见的请求。"""

    responses: Sequence[AssistantMessage]
    requests: list[ModelRequest] = field(default_factory=list)
    _next_response: int = 0

    async def complete(self, request: ModelRequest) -> AssistantMessage:
        self.requests.append(request)
        if self._next_response >= len(self.responses):
            raise RuntimeError("ScriptedProvider has no response left")
        response = self.responses[self._next_response]
        self._next_response += 1
        return response


@dataclass(frozen=True, slots=True)
class TraceEntry:
    event: str
    detail: str


@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    """同时返回本次调用产生的消息，以及最终模型上下文。"""

    new_messages: tuple[Message, ...]
    final_messages: tuple[Message, ...]
    trace: tuple[TraceEntry, ...]


# 工具异常必须变成模型能理解的 tool result，不能直接打断整个 Agent Loop。
async def _execute_tool(tool: Tool, call: ToolCall) -> ToolResultMessage:
    try:
        value = tool.execute(call.id, call.arguments)
        if inspect.isawaitable(value):
            value = await cast(Awaitable[str], value)
        return ToolResultMessage(call.id, call.name, cast(str, value))
    except Exception as error:  # 工具异常会转换成模型可见的结果。
        return ToolResultMessage(call.id, call.name, f"Tool error: {error}", is_error=True)


def _truncated_tool_result(call: ToolCall) -> ToolResultMessage:
    return ToolResultMessage(
        call.id,
        call.name,
        (
            f'Tool call "{call.name}" was not executed: the response hit the output '
            "token limit, so its arguments may be truncated."
        ),
        is_error=True,
    )


async def run_agent_loop(
    prompts: Sequence[UserMessage],
    context: AgentContext,
    provider: Provider,
) -> AgentLoopResult:
    """运行 prompt -> assistant -> tools -> assistant，直到不再产生工具调用。

    输入上下文会被复制；`new_messages` 只包含本次调用，`final_messages`
    则包含之前的 transcript。
    """

    # new_messages 是本次调用的增量；current_messages 才是发给模型的完整上下文。
    new_messages: list[Message] = list(prompts)
    current_messages: list[Message] = [*context.messages, *prompts]
    trace: list[TraceEntry] = [TraceEntry("agent_start", "run started")]

    trace.append(TraceEntry("turn_start", "provider turn 1"))
    for prompt in prompts:
        trace.extend(
            [
                TraceEntry("message_start", "user"),
                TraceEntry("message_end", f"user: {prompt.content}"),
            ]
        )

    turn = 1
    # 每轮只做一次 Provider 请求；有 tool call 时，tool result 会推动下一轮。
    while True:
        request = ModelRequest(
            system_prompt=context.system_prompt,
            messages=tuple(current_messages),
            tool_names=tuple(tool.name for tool in context.tools),
        )
        assistant = await provider.complete(request)
        current_messages.append(assistant)
        new_messages.append(assistant)
        trace.extend(
            [
                TraceEntry("message_start", "assistant"),
                TraceEntry("message_end", f"assistant: {assistant.stop_reason}"),
            ]
        )

        # error/aborted 是模型响应的终止原因，不能继续执行其中看似存在的工具调用。
        if assistant.stop_reason in {"error", "aborted"}:
            trace.append(TraceEntry("turn_end", "provider failed or was aborted"))
            break

        # 先收集并追加所有 tool result，再决定是否向 Provider 发起下一轮。
        tool_results: list[ToolResultMessage] = []
        for call in assistant.tool_calls:
            trace.append(TraceEntry("tool_execution_start", f"{call.name} ({call.id})"))

            if assistant.stop_reason == "length":
                result = _truncated_tool_result(call)
            else:
                tool = next((candidate for candidate in context.tools if candidate.name == call.name), None)
                if tool is None:
                    result = ToolResultMessage(
                        call.id,
                        call.name,
                        f'Tool "{call.name}" not found',
                        is_error=True,
                    )
                else:
                    result = await _execute_tool(tool, call)

            trace.extend(
                [
                    TraceEntry(
                        "tool_execution_end",
                        f"{call.name}: {'error' if result.is_error else 'ok'}",
                    ),
                    TraceEntry("message_start", "toolResult"),
                    TraceEntry("message_end", f"toolResult: {call.name}"),
                ]
            )
            tool_results.append(result)
            current_messages.append(result)
            new_messages.append(result)

        trace.append(TraceEntry("turn_end", f"{len(tool_results)} tool result(s)"))
        if not assistant.tool_calls:
            break

        turn += 1
        trace.append(TraceEntry("turn_start", f"provider turn {turn}"))

    trace.append(TraceEntry("agent_end", f"{len(new_messages)} new message(s)"))
    return AgentLoopResult(tuple(new_messages), tuple(current_messages), tuple(trace))


def _message_summary(message: Message) -> str:
    if isinstance(message, UserMessage):
        return f"user        {message.content}"
    if isinstance(message, ToolResultMessage):
        status = "error" if message.is_error else "ok"
        return f"toolResult  {message.tool_name} [{status}]: {message.content}"

    parts: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        else:
            parts.append(f"call {block.name}{dict(block.arguments)}")
    return f"assistant   {' | '.join(parts)}"


async def demo() -> None:
    virtual_files = {"hello.py": 'print("hello from Pi")\n'}

    def read_file(_call_id: str, arguments: Mapping[str, Any]) -> str:
        path = arguments.get("path")
        if not isinstance(path, str):
            raise ValueError("path must be a string")
        if path not in virtual_files:
            raise FileNotFoundError(path)
        return virtual_files[path]

    provider = ScriptedProvider(
        [
            AssistantMessage(
                (ToolCall("call-1", "read_file", {"path": "hello.py"}),),
                stop_reason="toolUse",
            ),
            AssistantMessage((TextBlock('The file prints "hello from Pi".'),)),
        ]
    )
    context = AgentContext(
        system_prompt="You are a coding agent.",
        messages=[],
        tools=[Tool("read_file", "Read a project file", read_file)],
    )

    result = await run_agent_loop([UserMessage("What does hello.py do?")], context, provider)

    print("s01: minimal agent loop\n")
    print("Trace")
    for index, entry in enumerate(result.trace, start=1):
        print(f"  {index:02d}. {entry.event:22} {entry.detail}")

    print("\nTranscript")
    for message in result.final_messages:
        print(f"  {_message_summary(message)}")

    print(f"\nProvider calls: {len(provider.requests)}")
    print(f"Input context unchanged: {context.messages == []}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
