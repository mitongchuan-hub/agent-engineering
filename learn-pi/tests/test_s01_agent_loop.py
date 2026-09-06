from __future__ import annotations

import asyncio

from s01_agent_loop.code import (
    AgentContext,
    AssistantMessage,
    ScriptedProvider,
    TextBlock,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    run_agent_loop,
)


def run(coro):
    return asyncio.run(coro)


def test_prompt_tool_result_then_final_assistant_closes_loop() -> None:
    provider = ScriptedProvider(
        [
            AssistantMessage((ToolCall("c1", "read", {"path": "a.txt"}),), "toolUse"),
            AssistantMessage((TextBlock("内容是 hello"),)),
        ]
    )
    context = AgentContext(
        system_prompt="You are a coding agent.",
        messages=[],
        tools=[Tool("read", "Read a file", lambda _id, _args: "hello")],
    )

    result = run(run_agent_loop([UserMessage("读取 a.txt")], context, provider))

    assert len(provider.requests) == 2
    assert [message.role for message in result.new_messages] == [
        "user",
        "assistant",
        "toolResult",
        "assistant",
    ]
    assert provider.requests[1].messages[-1].role == "toolResult"
    assert result.final_messages == result.new_messages
    assert [entry.event for entry in result.trace][-1] == "agent_end"


def test_existing_context_is_not_mutated_and_new_messages_are_scoped() -> None:
    old = UserMessage("历史问题")
    context = AgentContext("system", [old], [])
    provider = ScriptedProvider([AssistantMessage((TextBlock("回答"),))])

    result = run(run_agent_loop([UserMessage("新问题")], context, provider))

    assert context.messages == [old]
    assert [message.role for message in result.new_messages] == ["user", "assistant"]
    assert [message.role for message in result.final_messages] == ["user", "user", "assistant"]
    assert provider.requests[0].messages[0] == old


def test_provider_error_message_stops_before_tool_execution() -> None:
    executed: list[str] = []

    def execute(_id, _args):
        executed.append("called")
        return "must not run"

    provider = ScriptedProvider(
        [AssistantMessage((ToolCall("c1", "danger", {}),), "error", "upstream failed")]
    )
    context = AgentContext("system", [], [Tool("danger", "Dangerous tool", execute)])

    result = run(run_agent_loop([UserMessage("开始")], context, provider))

    assert executed == []
    assert len(provider.requests) == 1
    assert result.final_messages[-1].stop_reason == "error"
    assert "tool_execution_start" not in [entry.event for entry in result.trace]


def test_unknown_tool_becomes_error_result_and_loop_can_continue() -> None:
    provider = ScriptedProvider(
        [
            AssistantMessage((ToolCall("c1", "missing", {}),), "toolUse"),
            AssistantMessage((TextBlock("我无法读取该工具"),)),
        ]
    )
    result = run(run_agent_loop([UserMessage("调用不存在的工具")], AgentContext("", [], []), provider))

    tool_result = next(message for message in result.final_messages if isinstance(message, ToolResultMessage))
    assert tool_result.is_error is True
    assert "not found" in tool_result.content
    assert len(provider.requests) == 2


def test_length_stop_never_executes_truncated_tool_call() -> None:
    executed: list[str] = []

    def execute(_id, _args):
        executed.append("called")
        return "unsafe"

    provider = ScriptedProvider(
        [
            AssistantMessage((ToolCall("c1", "write", {"path": "a.txt"}),), "length"),
            AssistantMessage((TextBlock("请重新发起完整调用"),)),
        ]
    )
    context = AgentContext("", [], [Tool("write", "Write a file", execute)])

    result = run(run_agent_loop([UserMessage("写入")], context, provider))

    tool_result = next(message for message in result.final_messages if isinstance(message, ToolResultMessage))
    assert executed == []
    assert tool_result.is_error is True
    assert "token limit" in tool_result.content
    assert len(provider.requests) == 2


def test_tool_exception_is_returned_to_model_as_error() -> None:
    def execute(_id, _args):
        raise ValueError("permission denied")

    provider = ScriptedProvider(
        [
            AssistantMessage((ToolCall("c1", "read", {}),), "toolUse"),
            AssistantMessage((TextBlock("收到错误"),)),
        ]
    )
    result = run(
        run_agent_loop(
            [UserMessage("读取")],
            AgentContext("", [], [Tool("read", "Read", execute)]),
            provider,
        )
    )

    tool_result = next(message for message in result.final_messages if isinstance(message, ToolResultMessage))
    assert tool_result.is_error is True
    assert "permission denied" in tool_result.content
    assert provider.requests[1].messages[-1] == tool_result
