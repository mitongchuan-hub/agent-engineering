from __future__ import annotations

import asyncio

from s03_agent_events.code import (
    Agent,
    AgentEvent,
    AgentState,
    AssistantMessage,
    ScriptedRunner,
    ToolResultMessage,
    UserMessage,
    demo_events,
)


def run(coro):
    return asyncio.run(coro)


def test_state_reducer_tracks_transcript_and_pending_tools() -> None:
    async def scenario() -> None:
        agent = Agent(ScriptedRunner(demo_events("hello.py")))
        snapshots: list[tuple[str, bool, str | None, tuple[str, ...]]] = []

        def listener(event, _signal):
            snapshots.append(
                (
                    event.type,
                    agent.state.is_streaming,
                    type(agent.state.streaming_message).__name__
                    if agent.state.streaming_message is not None
                    else None,
                    tuple(sorted(agent.state.pending_tool_calls)),
                )
            )

        agent.subscribe(listener)
        await agent.prompt("hello.py")

        assert [message.role for message in agent.state.messages] == [
            "user",
            "assistant",
            "toolResult",
            "assistant",
        ]
        assert agent.state.is_streaming is False
        assert agent.state.streaming_message is None
        assert agent.state.pending_tool_calls == set()
        tool_start = next(snapshot for snapshot in snapshots if snapshot[0] == "tool_execution_start")
        assert tool_start[3] == ("call-1",)

    run(scenario())


def test_subscribers_run_in_registration_order_after_state_reduction() -> None:
    async def scenario() -> None:
        final = AssistantMessage("ok")
        events = (AgentEvent("agent_start"), AgentEvent("agent_end", messages=(final,)))
        agent = Agent(ScriptedRunner(events))
        calls: list[str] = []

        async def first(event, _signal):
            calls.append(f"first:{event.type}")
            await asyncio.sleep(0)

        def second(event, _signal):
            calls.append(f"second:{event.type}")

        agent.subscribe(first)
        agent.subscribe(second)
        await agent.prompt("hello")

        assert calls == ["first:agent_start", "second:agent_start", "first:agent_end", "second:agent_end"]

    run(scenario())


def test_prompt_resolves_only_after_agent_end_listener_and_then_becomes_idle() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        final = AssistantMessage("ok")
        agent = Agent(
            ScriptedRunner(
                (
                    AgentEvent("agent_start"),
                    AgentEvent("message_start", message=final),
                    AgentEvent("message_end", message=final),
                    AgentEvent("agent_end", messages=(final,)),
                )
            )
        )

        async def listener(event, _signal):
            if event.type == "agent_end":
                await release.wait()

        agent.subscribe(listener)
        prompt_task = asyncio.create_task(agent.prompt("hello"))
        await asyncio.sleep(0)
        while not agent.state.is_streaming:
            await asyncio.sleep(0)

        assert prompt_task.done() is False
        assert agent.state.is_streaming is True
        idle_task = asyncio.create_task(agent.wait_for_idle())
        await asyncio.sleep(0)
        assert idle_task.done() is False

        release.set()
        await asyncio.gather(prompt_task, idle_task)
        assert agent.state.is_streaming is False

    run(scenario())


def test_unsubscribe_stops_future_notifications() -> None:
    async def scenario() -> None:
        final = AssistantMessage("ok")
        agent = Agent(ScriptedRunner((AgentEvent("agent_start"), AgentEvent("agent_end"))))
        received: list[str] = []
        unsubscribe = agent.subscribe(lambda event, _signal: received.append(event.type))
        unsubscribe()

        await agent.prompt("hello")

        assert received == []

    run(scenario())


def test_thrown_runner_failure_is_converted_to_error_lifecycle() -> None:
    async def scenario() -> None:
        async def failing_runner(_prompt, emit, _signal):
            await emit(AgentEvent("agent_start"))
            await emit(AgentEvent("turn_start"))
            raise RuntimeError("provider exploded")

        agent = Agent(failing_runner)
        events: list[str] = []
        agent.subscribe(lambda event, _signal: events.append(event.type))

        await agent.prompt("hello")

        assert events == [
            "agent_start",
            "turn_start",
            "message_start",
            "message_end",
            "turn_end",
            "agent_end",
        ]
        assert isinstance(agent.state.messages[-1], AssistantMessage)
        assert agent.state.messages[-1].stop_reason == "error"
        assert agent.state.error_message == "provider exploded"
        assert agent.state.is_streaming is False

    run(scenario())


def test_second_prompt_is_rejected_while_first_run_is_active() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def slow_runner(_prompt, _emit, _signal):
            await release.wait()

        agent = Agent(slow_runner)
        first = asyncio.create_task(agent.prompt("first"))
        await asyncio.sleep(0)

        try:
            try:
                await agent.prompt("second")
            except RuntimeError as error:
                assert "already processing" in str(error)
            else:
                raise AssertionError("second prompt should be rejected")
        finally:
            release.set()
            await first

    run(scenario())


def test_listener_receives_active_abort_signal() -> None:
    async def scenario() -> None:
        signal_seen = []
        final = AssistantMessage("ok")
        agent = Agent(
            ScriptedRunner(
                (
                    AgentEvent("agent_start"),
                    AgentEvent("message_start", message=final),
                    AgentEvent("message_end", message=final),
                    AgentEvent("agent_end", messages=(final,)),
                )
            )
        )
        agent.subscribe(lambda _event, signal: signal_seen.append(signal))

        await agent.prompt("hello")

        assert signal_seen
        assert all(signal is signal_seen[0] for signal in signal_seen)
        assert signal_seen[0].aborted is False

    run(scenario())
