from __future__ import annotations

import asyncio

from s08_context_boundary.code import (
    AgentContext,
    AssistantMessage,
    BashExecutionMessage,
    BranchSummaryMessage,
    CompactionSummaryMessage,
    CustomMessage,
    NotificationMessage,
    ToolResultMessage,
    UserMessage,
    build_llm_context,
    convert_to_llm,
    keep_last,
)


def run(coro):
    return asyncio.run(coro)


def test_transform_runs_before_converter_and_converter_sees_transformed_list() -> None:
    async def scenario() -> None:
        order: list[str] = []
        seen: list[str] = []
        context = AgentContext("system", [UserMessage("old"), UserMessage("new")])

        def transform(messages):
            order.append("transform")
            return messages[-1:]

        def convert(messages):
            order.append("convert")
            seen.extend(message.content for message in messages if isinstance(message, UserMessage))
            return convert_to_llm(messages)

        result, traces = await build_llm_context(context, transform_context=transform, convert=convert)

        assert order == ["transform", "convert"]
        assert seen == ["new"]
        assert [message.content for message in result.messages] == ["new"]
        assert [(trace.stage, trace.input_count, trace.output_count) for trace in traces] == [
            ("transform_context", 2, 1),
            ("convert_to_llm", 1, 1),
        ]

    run(scenario())


def test_transform_does_not_modify_agent_transcript_container() -> None:
    async def scenario() -> None:
        messages = [UserMessage("one"), AssistantMessage("two"), UserMessage("three")]
        context = AgentContext("system", messages)

        result, _ = await build_llm_context(context, transform_context=lambda items: keep_last(items, 1))

        assert context.messages == messages
        assert [message.content for message in result.messages] == ["three"]

    run(scenario())


def test_ui_and_excluded_bash_messages_are_filtered() -> None:
    messages = [
        UserMessage("question"),
        NotificationMessage("spinner"),
        BashExecutionMessage("secret", "hidden", exclude_from_context=True),
        BashExecutionMessage("pytest", "ok"),
        CustomMessage("extension context", "note"),
    ]

    converted = convert_to_llm(messages)

    assert [message.role for message in converted] == ["user", "user", "user"]
    assert converted[0].content == "question"
    assert "Ran `pytest`" in converted[1].content
    assert converted[2].content == "extension context"
    assert all("spinner" not in message.content for message in converted)


def test_standard_messages_keep_order_and_tool_results_remain_model_visible() -> None:
    context = AgentContext(
        "system",
        [
            UserMessage("question"),
            AssistantMessage("calling"),
            ToolResultMessage("c1", "read", "file content"),
        ],
        ["read_file"],
    )

    result, _ = run(build_llm_context(context))

    assert [message.role for message in result.messages] == ["user", "assistant", "toolResult"]
    assert result.tool_names == ("read_file",)
    assert result.system_prompt == "system"


def test_branch_and_compaction_messages_become_marked_user_context() -> None:
    converted = convert_to_llm(
        [
            BranchSummaryMessage("branch facts", "node-1"),
            CompactionSummaryMessage("old facts", 1000),
        ]
    )

    assert all(message.role == "user" for message in converted)
    assert "branch facts" in converted[0].content
    assert "old facts" in converted[1].content
    assert "<summary>" in converted[0].content
    assert "<summary>" in converted[1].content


def test_async_transform_and_converter_are_supported() -> None:
    async def scenario() -> None:
        async def transform(messages):
            await asyncio.sleep(0)
            return messages

        async def convert(messages):
            await asyncio.sleep(0)
            return convert_to_llm(messages)

        result, traces = await build_llm_context(
            AgentContext("", [UserMessage("async")]),
            transform_context=transform,
            convert=convert,
        )

        assert result.messages[0].content == "async"
        assert len(traces) == 2

    run(scenario())


def test_transform_runs_again_for_each_model_request() -> None:
    async def scenario() -> None:
        calls = 0

        def transform(messages):
            nonlocal calls
            calls += 1
            return messages

        context = AgentContext("", [UserMessage("same")])
        await build_llm_context(context, transform_context=transform)
        await build_llm_context(context, transform_context=transform)

        assert calls == 2

    run(scenario())


def test_empty_transform_is_a_valid_empty_model_context() -> None:
    result, traces = run(
        build_llm_context(
            AgentContext("system", [UserMessage("not selected")]),
            transform_context=lambda _messages: [],
        )
    )

    assert result.messages == ()
    assert traces[-1].output_count == 0
