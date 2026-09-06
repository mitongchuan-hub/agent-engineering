from __future__ import annotations

import asyncio

from s04_tool_contract.code import (
    AbortSignal,
    BeforeToolCallResult,
    Tool,
    ToolCall,
    ToolOutcome,
    execute_tool_call,
    prepare_tool_call,
    validate_arguments,
)


def run(coro):
    return asyncio.run(coro)


SCHEMA = {
    "type": "object",
    "required": ["path"],
    "properties": {"path": {"type": "string", "minLength": 1}},
    "additionalProperties": False,
}


def make_tool(executed: list[dict]) -> Tool:
    return Tool(
        "read_file",
        "Read a file",
        SCHEMA,
        lambda _id, args: executed.append(args) or f"read {args['path']}",
    )


def test_missing_tool_is_an_immediate_error_without_execution() -> None:
    outcome = run(execute_tool_call([], ToolCall("c1", "missing", {})))

    assert isinstance(outcome, ToolOutcome)
    assert outcome.executed is False
    assert outcome.result.is_error is True
    assert "not found" in outcome.result.content


def test_invalid_arguments_are_rejected_before_execute() -> None:
    executed: list[dict] = []
    call = ToolCall("c1", "read_file", {"path": 42})

    outcome = run(execute_tool_call([make_tool(executed)], call))

    assert executed == []
    assert outcome.result.is_error is True
    assert "expected string" in outcome.result.content


def test_prepare_arguments_can_turn_shorthand_into_valid_arguments() -> None:
    executed: list[dict] = []
    tool = Tool(
        "read_file",
        "Read a file",
        SCHEMA,
        lambda _id, args: executed.append(args) or "ok",
        prepare_arguments=lambda args: {"path": args["file"]},
    )

    outcome = run(execute_tool_call([tool], ToolCall("c1", "read_file", {"file": "a.txt"})))

    assert outcome.executed is True
    assert executed == [{"path": "a.txt"}]


def test_validation_clones_arguments_before_returning_them() -> None:
    executed: list[dict] = []
    raw = {"path": "a.txt"}
    call = ToolCall("c1", "read_file", raw)
    validated = validate_arguments(make_tool(executed), call)

    validated["path"] = "changed.txt"

    assert raw == {"path": "a.txt"}


def test_before_hook_receives_validated_args_and_can_block_execution() -> None:
    executed: list[dict] = []
    seen: list[dict] = []

    def before(_call, args):
        seen.append(args)
        return BeforeToolCallResult(block=True, reason="policy denied", terminate=True)

    outcome = run(
        execute_tool_call(
            [make_tool(executed)],
            ToolCall("c1", "read_file", {"path": "a.txt"}),
            before_tool_call=before,
        )
    )

    assert seen == [{"path": "a.txt"}]
    assert executed == []
    assert outcome.result.content == "policy denied"
    assert outcome.result.terminate is True


def test_before_hook_mutation_is_used_without_revalidation() -> None:
    executed: list[dict] = []

    def before(_call, args):
        args["path"] = 123
        return None

    outcome = run(
        execute_tool_call(
            [make_tool(executed)],
            ToolCall("c1", "read_file", {"path": "a.txt"}),
            before_tool_call=before,
        )
    )

    assert outcome.executed is True
    assert executed == [{"path": 123}]


def test_tool_exception_becomes_error_result() -> None:
    def fail(_id, _args):
        raise PermissionError("permission denied")

    tool = Tool("read_file", "Read", SCHEMA, fail)
    outcome = run(execute_tool_call([tool], ToolCall("c1", "read_file", {"path": "a.txt"})))

    assert outcome.executed is False
    assert outcome.result.is_error is True
    assert outcome.result.tool_call_id == "c1"
    assert "permission denied" in outcome.result.content


def test_abort_after_before_hook_prevents_execution() -> None:
    executed: list[dict] = []
    signal = AbortSignal(True)

    outcome = run(
        execute_tool_call(
            [make_tool(executed)],
            ToolCall("c1", "read_file", {"path": "a.txt"}),
            signal=signal,
        )
    )

    assert executed == []
    assert outcome.result.content == "Operation aborted"
