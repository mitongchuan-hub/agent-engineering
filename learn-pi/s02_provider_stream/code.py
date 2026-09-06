#!/usr/bin/env python3
"""第 02 章：Pi 风格的 AssistantMessageEventStream 和 partial 组装。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar, cast


T = TypeVar("T")
R = TypeVar("R")
_MISSING = object()
_SENTINEL = object()


class EventStream(Generic[T, R]):
    # 事件消费和最终结果等待是两条独立通道：UI 可实时迭代，调用方也可直接 await result。
    """异步队列，同时提供终止事件和独立的最终结果 future。

    与 Pi 的 EventStream 一致：
    - 消费者尚未到达时，已推入的事件仍会排队；
    - 满足 `is_complete` 的事件会解析 `result()`；
    - 终止事件仍会交给迭代器；
    - 完成后继续 push 的事件会被忽略。
    """

    def __init__(self, is_complete: Callable[[T], bool], extract_result: Callable[[T], R]):
        self._is_complete = is_complete
        self._extract_result = extract_result
        self._queue: asyncio.Queue[object] = asyncio.Queue()
        self._done = False
        self._result_value: object = _MISSING
        self._result_future: asyncio.Future[R] | None = None

    def _resolve(self, value: R) -> None:
        if self._result_value is _MISSING:
            self._result_value = value
        if self._result_future is not None and not self._result_future.done():
            self._result_future.set_result(value)

    def push(self, event: T) -> None:
        if self._done:
            return

        # 完成事件先解析最终结果，但仍要交给 async iterator 消费。
        if self._is_complete(event):
            self._done = True
            self._resolve(self._extract_result(event))

        # 终止事件也进入队列，因此消费者不会看不到 done/error。
        self._queue.put_nowait(event)
        if self._done:
            self._queue.put_nowait(_SENTINEL)

    def end(self, result: R | object = _MISSING) -> None:
        if self._done:
            return
        self._done = True
        if result is not _MISSING:
            self._resolve(cast(R, result))
        self._queue.put_nowait(_SENTINEL)

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        item = await self._queue.get()
        if item is _SENTINEL:
            raise StopAsyncIteration
        return cast(T, item)

    async def result(self) -> R:
        """等待终止结果，不消费事件迭代器。"""

        if self._result_value is not _MISSING:
            return cast(R, self._result_value)
        if self._result_future is None:
            self._result_future = asyncio.get_running_loop().create_future()
        return await self._result_future


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    type: Literal["text"] = field(default="text", init=False)


@dataclass(frozen=True, slots=True)
class ThinkingBlock:
    text: str
    type: Literal["thinking"] = field(default="thinking", init=False)


@dataclass(frozen=True, slots=True)
class ToolCallBlock:
    id: str
    name: str
    arguments_json: str
    type: Literal["toolCall"] = field(default="toolCall", init=False)


AssistantBlock = TextBlock | ThinkingBlock | ToolCallBlock
StopReason = Literal["stop", "toolUse", "length", "error", "aborted"]


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    content: tuple[AssistantBlock, ...]
    stop_reason: StopReason = "stop"
    error_message: str | None = None

    def text(self) -> str:
        return "".join(block.text for block in self.content if isinstance(block, TextBlock))


EventType = Literal[
    "start",
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "toolcall_start",
    "toolcall_delta",
    "toolcall_end",
    "done",
    "error",
]


@dataclass(frozen=True, slots=True)
class AssistantStreamEvent:
    """Pi 的 AssistantMessageEvent 联合类型在 Python 中的投影。"""

    type: EventType
    partial: AssistantMessage | None = None
    content_index: int | None = None
    delta: str | None = None
    content: str | None = None
    message: AssistantMessage | None = None
    reason: StopReason | None = None


class AssistantMessageEventStream(EventStream[AssistantStreamEvent, AssistantMessage]):
    def __init__(self):
        super().__init__(
            is_complete=lambda event: event.type in {"done", "error"},
            extract_result=lambda event: event.message
            if event.message is not None
            else AssistantMessage((), "error", "terminal event has no message"),
        )


@dataclass(frozen=True, slots=True)
class AssemblyTrace:
    event: str
    detail: str


@dataclass(frozen=True, slots=True)
class AssembledResponse:
    final_message: AssistantMessage
    context_messages: tuple[AssistantMessage, ...]
    trace: tuple[AssemblyTrace, ...]


_UPDATE_EVENTS = {
    # 这些事件只更新当前 partial，不会结束一次 Provider 响应。
    "text_start",
    "text_delta",
    "text_end",
    "thinking_start",
    "thinking_delta",
    "thinking_end",
    "toolcall_start",
    "toolcall_delta",
    "toolcall_end",
}


async def assemble_assistant_response(
    stream: AssistantMessageEventStream,
    context_messages: list[AssistantMessage] | None = None,
) -> AssembledResponse:
    """重建 Pi `streamAssistantResponse` 的核心行为。

    `context_messages` 会像 Pi 的 AgentContext 一样被修改：收到 `start`
    时插入 partial，每次更新替换最后一项，终止消息拥有最终决定权。
    """

    messages = context_messages if context_messages is not None else []
    trace: list[AssemblyTrace] = []
    partial: AssistantMessage | None = None

    async for event in stream:
        # 先建立 partial，再用每个 update 替换 transcript 的最后一项。
        if event.type == "start":
            partial = event.partial or AssistantMessage(())
            messages.append(partial)
            trace.append(AssemblyTrace("message_start", partial.text()))
        elif event.type in _UPDATE_EVENTS:
            if partial is None:
                # 没有 start 就没有可更新的 partial，Pi 会忽略这类更新。
                trace.append(AssemblyTrace("ignored_update", event.type))
                continue
            partial = event.partial or partial
            if messages:
                messages[-1] = partial
            trace.append(AssemblyTrace("message_update", event.type))
        elif event.type in {"done", "error"}:
            final = await stream.result()
            if partial is None:
                messages.append(final)
                trace.append(AssemblyTrace("message_start", "terminal event without start"))
            else:
                messages[-1] = final
            trace.append(AssemblyTrace("message_end", final.stop_reason))
            return AssembledResponse(final, tuple(messages), tuple(trace))

    # 这个分支对应手动结束流并显式提供最终结果。
    final = await stream.result()
    if partial is None:
        messages.append(final)
        trace.append(AssemblyTrace("message_start", "manual terminal result"))
    else:
        messages[-1] = final
    trace.append(AssemblyTrace("message_end", final.stop_reason))
    return AssembledResponse(final, tuple(messages), tuple(trace))


def scripted_text_stream(text: str, *, delay: float = 0.0) -> AssistantMessageEventStream:
    """创建一个类似 Provider 的文本流，产生 text_start/delta/end/done 事件。"""

    stream = AssistantMessageEventStream()

    async def produce() -> None:
        # start 建立空响应；delta 逐步产生新的完整 partial 快照。
        empty = AssistantMessage(())
        stream.push(AssistantStreamEvent("start", partial=empty))
        stream.push(AssistantStreamEvent("text_start", partial=empty, content_index=0))

        built = ""
        for character in text:
            built += character
            partial = AssistantMessage((TextBlock(built),))
            stream.push(
                AssistantStreamEvent(
                    "text_delta",
                    partial=partial,
                    content_index=0,
                    delta=character,
                )
            )
            if delay:
                await asyncio.sleep(delay)

        final = AssistantMessage((TextBlock(text),), "stop")
        # done.message 是最终权威对象，不能依赖最后一次 delta 猜测终态。
        stream.push(
            AssistantStreamEvent("text_end", partial=final, content_index=0, content=text)
        )
        stream.push(AssistantStreamEvent("done", message=final, reason="stop"))

    asyncio.create_task(produce())
    return stream


async def demo() -> None:
    stream = scripted_text_stream("流式回答")
    result = await assemble_assistant_response(stream)

    print("s02: Provider stream and partial message assembly\n")
    print("Events")
    for number, entry in enumerate(result.trace, start=1):
        print(f"  {number:02d}. {entry.event:16} {entry.detail}")
    print(f"\nFinal message: {result.final_message.text()}")
    print(f"Stream result: { (await stream.result()).text() }")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
