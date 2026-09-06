from __future__ import annotations

import asyncio
import json

from s12_comprehensive.agent import ComprehensiveAgent
from s12_comprehensive.context import ContextPolicy
from s12_comprehensive.extensions import ExtensionAPI, load_extensions
from s12_comprehensive.models import (
    AssistantMessage,
    NotificationMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from s12_comprehensive.provider import ScriptedProvider
from s12_comprehensive.recovery import RecoveryPolicy
from s12_comprehensive.session import SessionStore
from s12_comprehensive.tools import ToolDefinition, ToolRegistry


def run(coro):
    return asyncio.run(coro)


def test_end_to_end_agent_executes_tool_then_uses_result(tmp_path) -> None:
    async def scenario() -> None:
        session = SessionStore.create("project", tmp_path / "session.jsonl")
        registry = ToolRegistry()
        registry.register(ToolDefinition("read", "读取", lambda args: f"内容:{args['path']}"))
        provider = ScriptedProvider(
            [
                AssistantMessage("先读文件", (ToolCall("c1", "read", {"path": "a.txt"}),), "toolUse"),
                AssistantMessage("文件内容已读取", stop_reason="stop"),
            ]
        )
        agent = ComprehensiveAgent(provider, registry, session)

        result = await agent.prompt("读取 a.txt")

        assert len(provider.requests) == 2
        assert isinstance(provider.requests[1].messages[-1], ToolResultMessage)
        assert [entry.data["message"]["role"] for entry in session.get_entries()] == [
            "user",
            "assistant",
            "toolResult",
            "assistant",
        ]
        assert result.events[-2].type == "agent_end"
        assert result.events[-1].type == "agent_settled"
        assert agent.is_streaming is False

    run(scenario())


def test_extension_tool_enters_same_registry_as_builtin_tool() -> None:
    registry = ToolRegistry()

    def extension(api: ExtensionAPI) -> None:
        api.register_tool(ToolDefinition("custom", "扩展工具", lambda _args: "extension result"))

    api = load_extensions(registry, [extension])

    assert registry.names() == ("custom",)
    assert [event.name for event in api.events] == ["session_start"]


def test_context_policy_filters_ui_messages_before_provider_request() -> None:
    policy = ContextPolicy()
    snapshot = policy.build(
        [UserMessage("question"), NotificationMessage("spinner"), AssistantMessage("answer")]
    )

    assert snapshot.transcript_count == 3
    assert snapshot.model_message_count == 2
    assert [message.role for message in snapshot.messages] == ["user", "assistant"]


def test_session_reload_preserves_comprehensive_transcript(tmp_path) -> None:
    path = tmp_path / "session.jsonl"
    session = SessionStore.create("project", path)
    session.append_message(UserMessage("question"))
    session.append_message(AssistantMessage("answer"))

    loaded = SessionStore.open(path)

    assert [message.content for message in loaded.context_messages()] == ["question", "answer"]
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["version"] == 3


def test_branch_keeps_original_path_and_changes_active_context() -> None:
    session = SessionStore("project")
    root = session.append_message(UserMessage("root"))
    answer = session.append_message(AssistantMessage("main"))
    abandoned = session.append_message(UserMessage("old branch"))
    session.branch(answer)
    session.append_message(UserMessage("new branch"))

    assert session.get_branch()[-1].data["message"]["content"] == "new branch"
    assert session.get_branch()[0].entry_id == root
    assert session.get_entries()[-2].entry_id == abandoned


def test_tool_batch_keeps_result_order_in_comprehensive_registry() -> None:
    async def scenario() -> None:
        async def slow(_args):
            await asyncio.sleep(0.02)
            return "slow"

        async def fast(_args):
            return "fast"

        registry = ToolRegistry()
        registry.register(ToolDefinition("slow", "慢", slow))
        registry.register(ToolDefinition("fast", "快", fast))
        result = await registry.execute_batch(
            [ToolCall("c1", "slow", {}), ToolCall("c2", "fast", {})]
        )

        assert result.execution_end_order == ("c2", "c1")
        assert [item.tool_call_id for item in result.results] == ["c1", "c2"]

    run(scenario())


def test_length_stop_compacts_and_retries_without_failed_response_in_context(tmp_path) -> None:
    async def scenario() -> None:
        session = SessionStore.create("project", tmp_path / "session.jsonl")
        for index in range(5):
            session.append_message(UserMessage(f"old-{index}"))
        provider = ScriptedProvider(
            [
                AssistantMessage("truncated", stop_reason="length"),
                AssistantMessage("recovered", stop_reason="stop"),
            ]
        )
        agent = ComprehensiveAgent(
            provider,
            ToolRegistry(),
            session,
            recovery_policy=RecoveryPolicy(max_context_messages=100, keep_recent_messages=2),
        )

        result = await agent.prompt("new")

        assert len(provider.requests) == 2
        second_request = provider.requests[1].messages
        assert all(message.content != "truncated" for message in second_request)
        assert any(event.type == "compaction_end" for event in result.events)
        assert result.events[-1].type == "agent_settled"

    run(scenario())


def test_provider_exception_is_recorded_as_error_and_settled(tmp_path) -> None:
    async def scenario() -> None:
        session = SessionStore.create("project", tmp_path / "session.jsonl")
        provider = ScriptedProvider([])
        agent = ComprehensiveAgent(provider, ToolRegistry(), session)

        result = await agent.prompt("hello")

        assert isinstance(result.messages[-1], AssistantMessage)
        assert result.messages[-1].stop_reason == "error"
        assert result.messages[-1].error_message == "ScriptedProvider 没有剩余响应"
        assert result.events[-1].type == "agent_settled"

    run(scenario())


def test_dynamic_extension_is_available_to_agent_prompt(tmp_path) -> None:
    async def scenario() -> None:
        registry = ToolRegistry()

        def extension(api: ExtensionAPI) -> None:
            api.register_tool(ToolDefinition("echo", "回显", lambda args: args["text"]))

        load_extensions(registry, [extension])
        session = SessionStore.create("project", tmp_path / "session.jsonl")
        provider = ScriptedProvider(
            [
                AssistantMessage("call", (ToolCall("c1", "echo", {"text": "ok"}),), "toolUse"),
                AssistantMessage("done"),
            ]
        )
        result = await ComprehensiveAgent(provider, registry, session).prompt("echo")

        assert any(message.content == "ok" for message in result.messages if isinstance(message, ToolResultMessage))

    run(scenario())
