#!/usr/bin/env python3
"""第 06 章：Steering/Follow-up 队列及其循环 drain 边界。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

QueueMode = Literal["all", "one-at-a-time"]


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str
    source: Literal["user", "steering", "follow-up"] = "user"
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    tool_calls: tuple[str, ...] = ()
    role: Literal["assistant"] = field(default="assistant", init=False)


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_name: str
    text: str
    role: Literal["toolResult"] = field(default="toolResult", init=False)


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


class PendingMessageQueue:
    """Pi 的队列语义：一次 drain 全部消息，或只取最老的一条。"""

    def __init__(self, mode: QueueMode = "one-at-a-time") -> None:
        self.mode = mode
        self._messages: list[UserMessage] = []

    def enqueue(self, message: UserMessage) -> None:
        self._messages.append(message)

    def has_items(self) -> bool:
        return bool(self._messages)

    def drain(self) -> list[UserMessage]:
        if self.mode == "all":
            # all 模式一次性交付当前快照；后续入队消息留到下一次 drain。
            drained = self._messages[:]
            self._messages.clear()
            return drained
        if not self._messages:
            return []
        # one-at-a-time 保留剩余消息，让每条 steering 各自获得一个注入机会。
        return [self._messages.pop(0)]

    def clear(self) -> None:
        self._messages.clear()


@dataclass(frozen=True, slots=True)
class ModelRequest:
    call_number: int
    messages: tuple[Message, ...]


class ScriptedProvider:
    """一个可以在模型响应后向队列追加消息的 Provider 桩。"""

    def __init__(
        self,
        responses: Sequence[AssistantMessage],
        after_response: Callable[[int, AssistantMessage], None | Awaitable[None]] | None = None,
    ) -> None:
        self.responses = tuple(responses)
        self.after_response = after_response
        self.requests: list[ModelRequest] = []

    async def complete(self, messages: Sequence[Message]) -> AssistantMessage:
        number = len(self.requests) + 1
        request = ModelRequest(number, tuple(messages))
        self.requests.append(request)
        try:
            response = self.responses[number - 1]
        except IndexError as error:
            raise RuntimeError("ScriptedProvider has no response left") from error
        if self.after_response is not None:
            result = self.after_response(number, response)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]
        return response


@dataclass(frozen=True, slots=True)
class QueueTrace:
    event: str
    detail: str


@dataclass(frozen=True, slots=True)
class QueueLoopResult:
    messages: tuple[Message, ...]
    requests: tuple[ModelRequest, ...]
    trace: tuple[QueueTrace, ...]


async def run_queue_loop(
    prompt: UserMessage,
    provider: ScriptedProvider,
    steering_queue: PendingMessageQueue,
    follow_up_queue: PendingMessageQueue,
    *,
    prepare_next_turn: Callable[[int], None | Awaitable[None]] | None = None,
) -> QueueLoopResult:
    """运行 Pi `runLoop` 中与队列相关的部分。

    Steering 在第一次模型请求前和每次完成 turn 后检查；Follow-up 只在
    Agent 原本要停止时检查。
    """

    messages: list[Message] = [prompt]
    trace: list[QueueTrace] = [QueueTrace("agent_start", "run started")]
    # 首次 Provider 请求前也要检查 steering，用户可能在等待期间已经输入消息。
    pending: list[UserMessage] = steering_queue.drain()
    turn_number = 0
    last_completed_turn = False

    while True:
        # 内循环负责 tool call 和 steering；外循环只负责 follow-up。
        has_more_tool_calls = True
        while has_more_tool_calls or pending:
            if last_completed_turn:
                if prepare_next_turn is not None:
                    result = prepare_next_turn(turn_number)
                    if hasattr(result, "__await__"):
                        await result  # type: ignore[misc]
                    trace.append(QueueTrace("prepare_next_turn", str(turn_number)))
                if not pending:
                    pending = steering_queue.drain()
                    if pending:
                        trace.append(QueueTrace("steering_poll", str(len(pending))))
                trace.append(QueueTrace("turn_start", str(turn_number + 1)))

            if pending:
                source = pending[0].source
                for queued in pending:
                    messages.append(queued)
                    trace.append(QueueTrace(f"inject_{source}", queued.text))
                pending = []

            turn_number += 1
            trace.append(QueueTrace("provider_call", str(turn_number)))
            assistant = await provider.complete(messages)
            messages.append(assistant)
            trace.append(QueueTrace("assistant", assistant.text))

            tool_results: list[ToolResultMessage] = []
            for tool_name in assistant.tool_calls:
                result = ToolResultMessage(tool_name, f"result from {tool_name}")
                messages.append(result)
                tool_results.append(result)
                trace.append(QueueTrace("tool_result", tool_name))
            has_more_tool_calls = bool(tool_results)
            trace.append(QueueTrace("turn_end", str(len(tool_results))))
            last_completed_turn = True

            # 这里是 steering 的 drain 点；当前 assistant 的工具调用已经先处理完。
            pending = steering_queue.drain()
            if pending:
                trace.append(QueueTrace("steering_poll", str(len(pending))))

        trace.append(QueueTrace("follow_up_poll", "drain"))
        # 只有 Agent 原本会停止时，才允许 follow-up 开启新的外层轮次。
        pending = follow_up_queue.drain()
        if pending:
            trace.append(QueueTrace("follow_up_found", str(len(pending))))
            continue
        break

    trace.append(QueueTrace("agent_end", "run finished"))
    return QueueLoopResult(tuple(messages), tuple(provider.requests), tuple(trace))


def _texts(messages: Sequence[Message]) -> list[str]:
    return [message.text for message in messages if isinstance(message, UserMessage)]


async def demo() -> None:
    steering = PendingMessageQueue("one-at-a-time")
    steering.enqueue(UserMessage("先检查测试", "steering"))
    steering.enqueue(UserMessage("再检查 diff", "steering"))
    follow_up = PendingMessageQueue("one-at-a-time")
    follow_up.enqueue(UserMessage("最后总结", "follow-up"))

    provider = ScriptedProvider(
        [AssistantMessage("完成一项"), AssistantMessage("完成另一项"), AssistantMessage("总结完成")]
    )
    result = await run_queue_loop(
        UserMessage("开始工作"),
        provider,
        steering,
        follow_up,
    )

    print("s06: steering and follow-up queue semantics\n")
    print("User messages by provider request")
    for request in result.requests:
        print(f"  call {request.call_number}: {_texts(request.messages)}")
    print("\nQueue trace")
    for item in result.trace:
        if item.event in {"inject_steering", "inject_follow-up", "follow_up_found", "follow_up_poll"}:
            print(f"  {item.event:18} {item.detail}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
