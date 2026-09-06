#!/usr/bin/env python3
"""第 08 章：Agent transcript 到 LLM context 的边界。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
import inspect
from typing import Literal, TypeAlias, cast


@dataclass(frozen=True, slots=True)
class UserMessage:
    content: str
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    content: str
    role: Literal["assistant"] = field(default="assistant", init=False)


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    role: Literal["toolResult"] = field(default="toolResult", init=False)


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """只给 UI 使用的消息，不应进入模型上下文。"""

    content: str
    role: Literal["notification"] = field(default="notification", init=False)


@dataclass(frozen=True, slots=True)
class CustomMessage:
    content: str
    custom_type: str
    display: bool = True
    role: Literal["custom"] = field(default="custom", init=False)


@dataclass(frozen=True, slots=True)
class BashExecutionMessage:
    command: str
    output: str
    exit_code: int | None = 0
    cancelled: bool = False
    truncated: bool = False
    full_output_path: str | None = None
    exclude_from_context: bool = False
    role: Literal["bashExecution"] = field(default="bashExecution", init=False)


@dataclass(frozen=True, slots=True)
class BranchSummaryMessage:
    summary: str
    from_id: str | None = None
    role: Literal["branchSummary"] = field(default="branchSummary", init=False)


@dataclass(frozen=True, slots=True)
class CompactionSummaryMessage:
    summary: str
    tokens_before: int
    role: Literal["compactionSummary"] = field(default="compactionSummary", init=False)


AgentMessage: TypeAlias = (
    UserMessage
    | AssistantMessage
    | ToolResultMessage
    | NotificationMessage
    | CustomMessage
    | BashExecutionMessage
    | BranchSummaryMessage
    | CompactionSummaryMessage
)
LLMMessage: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(slots=True)
class AgentContext:
    system_prompt: str
    messages: list[AgentMessage]
    tool_names: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LLMContext:
    system_prompt: str
    messages: tuple[LLMMessage, ...]
    tool_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PipelineTrace:
    stage: Literal["transform_context", "convert_to_llm"]
    input_count: int
    output_count: int


TransformContext: TypeAlias = Callable[
    [list[AgentMessage]], list[AgentMessage] | Awaitable[list[AgentMessage]]
]
ConvertToLlm: TypeAlias = Callable[
    [list[AgentMessage]], list[LLMMessage] | Awaitable[list[LLMMessage]]
]

COMPACTION_PREFIX = "The conversation history before this point was compacted into the following summary:\n<summary>\n"
COMPACTION_SUFFIX = "\n</summary>"
BRANCH_PREFIX = "The following is a summary of a branch that this conversation came back from:\n<summary>\n"
BRANCH_SUFFIX = "\n</summary>"


def bash_execution_to_text(message: BashExecutionMessage) -> str:
    text = f"Ran `{message.command}`\n"
    text += f"```\n{message.output}\n```" if message.output else "(no output)"
    if message.cancelled:
        text += "\n\n(command cancelled)"
    elif message.exit_code is not None and message.exit_code != 0:
        text += f"\n\nCommand exited with code {message.exit_code}"
    if message.truncated and message.full_output_path:
        text += f"\n\n[Output truncated. Full output: {message.full_output_path}]"
    return text


def convert_to_llm(messages: list[AgentMessage]) -> list[LLMMessage]:
    """把完整 Agent 消息映射为 Provider 可接受的消息。"""

    converted: list[LLMMessage] = []
    for message in messages:
        if isinstance(message, NotificationMessage):
            # UI 通知不属于模型上下文。
            continue
        if isinstance(message, BashExecutionMessage):
            if message.exclude_from_context:
                continue
            converted.append(UserMessage(bash_execution_to_text(message)))
        elif isinstance(message, CustomMessage):
            converted.append(UserMessage(message.content))
        elif isinstance(message, BranchSummaryMessage):
            converted.append(UserMessage(BRANCH_PREFIX + message.summary + BRANCH_SUFFIX))
        elif isinstance(message, CompactionSummaryMessage):
            converted.append(UserMessage(COMPACTION_PREFIX + message.summary + COMPACTION_SUFFIX))
        else:
            # user、assistant、toolResult 原样通过。
            converted.append(cast(LLMMessage, message))
    return converted


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def build_llm_context(
    context: AgentContext,
    *,
    transform_context: TransformContext | None = None,
    convert: ConvertToLlm = convert_to_llm,
) -> tuple[LLMContext, tuple[PipelineTrace, ...]]:
    """按 Pi 的顺序执行 transform，再执行 convert。"""

    # 复制列表，让本章的 transform 示例不会直接改写 AgentContext 容器。
    working = list(context.messages)
    traces: list[PipelineTrace] = []
    if transform_context is not None:
        transformed = await _await_if_needed(transform_context(working))
        working = list(transformed)
        traces.append(PipelineTrace("transform_context", len(context.messages), len(working)))

    converted = await _await_if_needed(convert(working))
    llm_messages = list(converted)
    traces.append(PipelineTrace("convert_to_llm", len(working), len(llm_messages)))
    return (
        LLMContext(context.system_prompt, tuple(llm_messages), tuple(context.tool_names)),
        tuple(traces),
    )


def keep_last(messages: list[AgentMessage], limit: int) -> list[AgentMessage]:
    """一个教学用裁剪器；真实 token/语义压缩在后续章节处理。"""

    if limit <= 0:
        return []
    return messages[-limit:]


async def demo() -> None:
    context = AgentContext(
        system_prompt="You are a coding agent.",
        messages=[
            UserMessage("检查项目"),
            AssistantMessage("我先运行测试"),
            BashExecutionMessage("pytest", "2 passed"),
            NotificationMessage("测试面板已刷新"),
            CustomMessage("请关注失败用例", "hint"),
        ],
        tool_names=["read", "bash"],
    )
    llm_context, traces = await build_llm_context(
        context,
        transform_context=lambda messages: keep_last(messages, 4),
    )

    print("s08: context transform and LLM conversion\n")
    print(f"Agent transcript: {[message.role for message in context.messages]}")
    print(f"LLM messages: {[message.role for message in llm_context.messages]}")
    print(f"LLM text: {[getattr(message, 'content', '') for message in llm_context.messages]}")
    print(f"Pipeline: {[(trace.stage, trace.input_count, trace.output_count) for trace in traces]}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
