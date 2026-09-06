from __future__ import annotations

import asyncio

from s07_control_boundaries.code import (
    AgentCore,
    AgentSession,
    AgentEvent,
    AssistantMessage,
    RunPlan,
    UserMessage,
)


def run(coro):
    return asyncio.run(coro)


def test_stop_emits_agent_end_then_agent_settled() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(core, [RunPlan(AssistantMessage("done", "stop"))])

        await session.prompt("hello")

        assert [event.type for event in session.events] == ["agent_end", "agent_settled"]
        assert session.is_idle is True
        assert core.state.is_streaming is False

    run(scenario())


def test_agent_end_is_not_settled_when_retry_is_pending() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(
            core,
            [
                RunPlan(AssistantMessage("failed", "error", "timeout"), after="retry"),
                RunPlan(AssistantMessage("recovered", "stop")),
            ],
        )
        observed: list[str] = []
        session.subscribe(lambda event: observed.append(event.type))

        await session.prompt("hello")

        assert observed == [
            "agent_end",
            "auto_retry_start",
            "agent_end",
            "agent_settled",
        ]
        assert [message.text for message in core.state.messages if isinstance(message, AssistantMessage)] == [
            "failed",
            "recovered",
        ]

    run(scenario())


def test_compaction_is_between_agent_end_and_agent_settled() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(
            core,
            [
                RunPlan(AssistantMessage("too long", "length"), after="compaction"),
                RunPlan(AssistantMessage("after compact", "stop")),
            ],
        )

        await session.prompt("hello")
        events = [event.type for event in session.events]

        assert events == [
            "agent_end",
            "compaction_start",
            "compaction_end",
            "agent_end",
            "agent_settled",
        ]

    run(scenario())


def test_async_agent_end_listener_delays_core_idle() -> None:
    async def scenario() -> None:
        barrier = asyncio.Event()
        core = AgentCore()
        session = AgentSession(core, [RunPlan(AssistantMessage("done", "stop"))])

        async def listener(event, _signal):
            if event.type == "agent_end":
                await barrier.wait()

        core.subscribe(listener)
        task = asyncio.create_task(session.prompt("hello"))
        await asyncio.sleep(0)
        while not core.state.is_streaming:
            await asyncio.sleep(0)

        assert task.done() is False
        assert session.is_idle is False
        assert core.state.is_streaming is True

        barrier.set()
        await task
        assert core.state.is_streaming is False
        assert session.is_idle is True

    run(scenario())


def test_abort_produces_aborted_message_and_still_settles() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(
            core,
            [RunPlan(AssistantMessage("never returned", "stop"), wait_for_abort=True)],
        )
        task = asyncio.create_task(session.prompt("hello"))
        await asyncio.sleep(0)
        while core.signal is None:
            await asyncio.sleep(0)

        await session.abort_and_wait()
        await task

        last = core.state.messages[-1]
        assert isinstance(last, AssistantMessage)
        assert last.stop_reason == "aborted"
        assert [event.type for event in session.events] == ["agent_end", "agent_settled"]
        assert session.is_idle is True

    run(scenario())


def test_thrown_runner_error_is_normalized_before_settlement() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(
            core,
            [RunPlan(AssistantMessage("unused", "stop"), throw_error="provider exploded")],
        )
        await session.prompt("hello")

        last = core.state.messages[-1]
        assert isinstance(last, AssistantMessage)
        assert last.stop_reason == "error"
        assert last.error_message == "provider exploded"
        assert core.state.error_message == "provider exploded"

    run(scenario())


def test_second_prompt_is_rejected_while_session_is_active() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(core, [RunPlan(AssistantMessage("done", "stop"))])
        # Hold the low-level run at agent_end so the outer session remains active.
        barrier = asyncio.Event()
        core.subscribe(
            lambda event, _signal: barrier.wait() if event.type == "agent_end" else None
        )
        first = asyncio.create_task(session.prompt("first"))
        await asyncio.sleep(0)
        while session.is_idle:
            await asyncio.sleep(0)

        try:
            await session.prompt("second")
        except RuntimeError as error:
            assert "already processing" in str(error)
        else:
            raise AssertionError("second prompt should be rejected")
        finally:
            barrier.set()
            await first

    run(scenario())


def test_core_event_order_has_agent_end_before_session_settled() -> None:
    async def scenario() -> None:
        core = AgentCore()
        session = AgentSession(core, [RunPlan(AssistantMessage("ok", "stop"))])
        core_events: list[str] = []
        core.subscribe(lambda event, _signal: core_events.append(event.type))

        await session.prompt("hello")

        assert core_events[-1] == "agent_end"
        assert session.events[-1].type == "agent_settled"
        assert isinstance(core.state.messages[0], UserMessage)

    run(scenario())
