from __future__ import annotations

import asyncio

from s02_provider_stream.code import (
    AssistantMessage,
    AssistantMessageEventStream,
    AssistantStreamEvent,
    EventStream,
    TextBlock,
    assemble_assistant_response,
    scripted_text_stream,
)


def run(coro):
    return asyncio.run(coro)


def test_terminal_event_is_delivered_and_resolves_result() -> None:
    async def scenario() -> None:
        stream: EventStream[str, str] = EventStream(lambda event: event == "done", lambda event: event)
        stream.push("queued")
        stream.push("done")
        stream.push("ignored")

        events = [event async for event in stream]

        assert events == ["queued", "done"]
        assert await stream.result() == "done"

    run(scenario())


def test_manual_end_can_provide_result_without_a_complete_event() -> None:
    async def scenario() -> None:
        stream: EventStream[str, str] = EventStream(lambda _event: False, lambda event: event)
        stream.push("progress")
        stream.end("manual result")

        assert [event async for event in stream] == ["progress"]
        assert await stream.result() == "manual result"

    run(scenario())


def test_consumer_can_wait_while_provider_pushes_incremental_events() -> None:
    async def scenario() -> None:
        stream = scripted_text_stream("abc", delay=0)
        events = [event async for event in stream]

        assert [event.type for event in events] == [
            "start",
            "text_start",
            "text_delta",
            "text_delta",
            "text_delta",
            "text_end",
            "done",
        ]
        assert events[2].delta == "a"
        assert events[4].partial is not None
        assert events[4].partial.text() == "abc"

    run(scenario())


def test_assembler_replaces_partial_messages_and_uses_done_as_authority() -> None:
    async def scenario() -> None:
        stream = AssistantMessageEventStream()
        initial = AssistantMessage(())
        stream.push(AssistantStreamEvent("start", partial=initial))
        stream.push(
            AssistantStreamEvent(
                "text_delta",
                partial=AssistantMessage((TextBlock("partial"),)),
                delta="partial",
                content_index=0,
            )
        )
        authoritative = AssistantMessage((TextBlock("final"),), "stop")
        stream.push(AssistantStreamEvent("done", message=authoritative, reason="stop"))

        context: list[AssistantMessage] = []
        result = await assemble_assistant_response(stream, context)

        assert context == [authoritative]
        assert result.final_message is authoritative
        assert [item.event for item in result.trace] == [
            "message_start",
            "message_update",
            "message_end",
        ]

    run(scenario())


def test_error_is_a_terminal_stream_event_and_final_message_is_error() -> None:
    async def scenario() -> None:
        stream = AssistantMessageEventStream()
        partial = AssistantMessage((TextBlock("before failure"),))
        stream.push(AssistantStreamEvent("start", partial=partial))
        error = AssistantMessage((), "error", "upstream failed")
        stream.push(AssistantStreamEvent("error", message=error, reason="error"))
        stream.push(AssistantStreamEvent("text_delta", partial=partial, delta="ignored"))

        result = await assemble_assistant_response(stream)

        assert result.final_message.stop_reason == "error"
        assert result.final_message.error_message == "upstream failed"
        assert [item.event for item in result.trace] == ["message_start", "message_end"]

    run(scenario())


def test_done_without_start_still_emits_message_start() -> None:
    async def scenario() -> None:
        stream = AssistantMessageEventStream()
        final = AssistantMessage((TextBlock("direct"),), "stop")
        stream.push(AssistantStreamEvent("done", message=final, reason="stop"))

        result = await assemble_assistant_response(stream)

        assert result.context_messages == (final,)
        assert result.trace[0].event == "message_start"
        assert result.trace[0].detail == "terminal event without start"

    run(scenario())
