from __future__ import annotations

import asyncio

from s06_message_queues.code import (
    AssistantMessage,
    PendingMessageQueue,
    ScriptedProvider,
    UserMessage,
    run_queue_loop,
)


def run(coro):
    return asyncio.run(coro)


def test_all_mode_drains_every_message_at_once() -> None:
    queue = PendingMessageQueue("all")
    queue.enqueue(UserMessage("one", "steering"))
    queue.enqueue(UserMessage("two", "steering"))

    assert [message.text for message in queue.drain()] == ["one", "two"]
    assert queue.drain() == []


def test_one_at_a_time_drains_oldest_and_keeps_remaining() -> None:
    queue = PendingMessageQueue("one-at-a-time")
    queue.enqueue(UserMessage("one", "steering"))
    queue.enqueue(UserMessage("two", "steering"))

    assert [message.text for message in queue.drain()] == ["one"]
    assert queue.has_items() is True
    assert [message.text for message in queue.drain()] == ["two"]
    assert queue.has_items() is False


def test_initial_steering_is_injected_before_first_provider_request() -> None:
    async def scenario() -> None:
        steering = PendingMessageQueue("all")
        steering.enqueue(UserMessage("steer one", "steering"))
        steering.enqueue(UserMessage("steer two", "steering"))
        provider = ScriptedProvider([AssistantMessage("done")])

        result = await run_queue_loop(
            UserMessage("prompt"), provider, steering, PendingMessageQueue()
        )

        assert [message.text for message in provider.requests[0].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "steer one",
            "steer two",
        ]
        assert [item.event for item in result.trace].index("inject_steering") < [
            item.event for item in result.trace
        ].index("provider_call")

    run(scenario())


def test_one_at_a_time_steering_creates_one_turn_per_message() -> None:
    async def scenario() -> None:
        steering = PendingMessageQueue("one-at-a-time")
        steering.enqueue(UserMessage("first steering", "steering"))
        steering.enqueue(UserMessage("second steering", "steering"))
        provider = ScriptedProvider([AssistantMessage("a"), AssistantMessage("b")])

        await run_queue_loop(UserMessage("prompt"), provider, steering, PendingMessageQueue())

        assert len(provider.requests) == 2
        assert [message.text for message in provider.requests[0].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "first steering",
        ]
        assert [message.text for message in provider.requests[1].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "first steering",
            "second steering",
        ]

    run(scenario())


def test_steering_waits_until_current_tool_calls_finish() -> None:
    async def scenario() -> None:
        steering = PendingMessageQueue()

        def after_response(number, _response):
            if number == 1:
                steering.enqueue(UserMessage("steer while tool runs", "steering"))

        provider = ScriptedProvider(
            [
                AssistantMessage("need tool", ("read_file",)),
                AssistantMessage("steering handled"),
            ],
            after_response,
        )
        result = await run_queue_loop(UserMessage("prompt"), provider, steering, PendingMessageQueue())

        # The next request includes the tool result and then the queued
        # steering message; there is no extra empty model turn.
        assert [message.text for message in provider.requests[1].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "steer while tool runs",
        ]
        assert [item.event for item in result.trace].index("tool_result") < [
            item.event for item in result.trace
        ].index("inject_steering")

    run(scenario())


def test_follow_up_runs_only_after_agent_would_otherwise_stop() -> None:
    async def scenario() -> None:
        follow_up = PendingMessageQueue()
        follow_up.enqueue(UserMessage("follow up", "follow-up"))
        provider = ScriptedProvider([AssistantMessage("first"), AssistantMessage("followed")])

        result = await run_queue_loop(UserMessage("prompt"), provider, PendingMessageQueue(), follow_up)

        assert len(provider.requests) == 2
        assert [message.text for message in provider.requests[0].messages if isinstance(message, UserMessage)] == [
            "prompt",
        ]
        assert [message.text for message in provider.requests[1].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "follow up",
        ]
        events = [item.event for item in result.trace]
        assert events.index("follow_up_poll") < events.index("follow_up_found") < events.index("inject_follow-up")

    run(scenario())


def test_follow_up_waits_behind_remaining_tool_turn() -> None:
    async def scenario() -> None:
        follow_up = PendingMessageQueue()
        follow_up.enqueue(UserMessage("after all tools", "follow-up"))
        provider = ScriptedProvider(
            [AssistantMessage("call", ("read",)), AssistantMessage("final"), AssistantMessage("follow-up final")]
        )

        await run_queue_loop(UserMessage("prompt"), provider, PendingMessageQueue(), follow_up)

        assert len(provider.requests) == 3
        assert [message.text for message in provider.requests[1].messages if isinstance(message, UserMessage)] == [
            "prompt",
        ]
        assert [message.text for message in provider.requests[2].messages if isinstance(message, UserMessage)] == [
            "prompt",
            "after all tools",
        ]

    run(scenario())


def test_steering_is_served_before_follow_up() -> None:
    async def scenario() -> None:
        steering = PendingMessageQueue()
        steering.enqueue(UserMessage("urgent", "steering"))
        follow_up = PendingMessageQueue()
        follow_up.enqueue(UserMessage("later", "follow-up"))
        provider = ScriptedProvider([AssistantMessage("first"), AssistantMessage("urgent done"), AssistantMessage("later done")])

        await run_queue_loop(UserMessage("prompt"), provider, steering, follow_up)

        user_batches = [
            [message.text for message in request.messages if isinstance(message, UserMessage)]
            for request in provider.requests
        ]
        assert user_batches == [["prompt", "urgent"], ["prompt", "urgent", "later"]]

    run(scenario())


def test_prepare_next_turn_runs_before_each_queued_next_turn() -> None:
    async def scenario() -> None:
        seen: list[int] = []
        follow_up = PendingMessageQueue()
        follow_up.enqueue(UserMessage("later", "follow-up"))
        provider = ScriptedProvider([AssistantMessage("first"), AssistantMessage("later")])

        await run_queue_loop(
            UserMessage("prompt"),
            provider,
            PendingMessageQueue(),
            follow_up,
            prepare_next_turn=lambda number: seen.append(number),
        )

        assert seen == [1]

    run(scenario())
