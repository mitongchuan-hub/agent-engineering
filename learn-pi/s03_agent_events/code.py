#!/usr/bin/env python3
"""第 03 章：Agent 生命周期事件与状态归约。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
import inspect
from typing import Literal, TypeAlias


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    stop_reason: Literal["stop", "toolUse", "error", "aborted"] = "stop"
    error_message: str | None = None
    role: Literal["assistant"] = field(default="assistant", init=False)


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    text: str
    is_error: bool = False
    role: Literal["toolResult"] = field(default="toolResult", init=False)


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage
EventType = Literal[
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "message_start",
    "message_update",
    "message_end",
    "tool_execution_start",
    "tool_execution_update",
    "tool_execution_end",
]


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: EventType
    message: Message | None = None
    messages: tuple[Message, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    partial_result: str | None = None
    is_error: bool = False
    tool_results: tuple[ToolResultMessage, ...] = ()


class AbortSignal:
    """传给 Pi listener 的离线版 signal。"""

    def __init__(self) -> None:
        self.aborted = False

    def abort(self) -> None:
        self.aborted = True


AgentListener: TypeAlias = Callable[[AgentEvent, AbortSignal], None | Awaitable[None]]
EventSink: TypeAlias = Callable[[AgentEvent], Awaitable[None]]
Runner: TypeAlias = Callable[[str, EventSink, AbortSignal], Awaitable[None]]


@dataclass(slots=True)
class AgentState:
    # messages 只放已结束消息；streaming_message 保存当前尚未结束的快照。
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    streaming_message: Message | None = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error_message: str | None = None


class Agent:
    """在通知 listener 前先归约生命周期事件的有状态 Agent 外壳。"""

    def __init__(self, runner: Runner, initial_state: AgentState | None = None):
        initial = initial_state or AgentState()
        # 复制初始数组，避免外部调用者通过原列表绕过 Agent 的状态边界。
        self.state = AgentState(
            system_prompt=initial.system_prompt,
            messages=list(initial.messages),
            is_streaming=False,
            streaming_message=None,
            pending_tool_calls=set(),
            error_message=None,
        )
        self._runner = runner
        self._listeners: list[AgentListener] = []
        self._active = False
        self._signal: AbortSignal | None = None
        self._idle_future: asyncio.Future[None] | None = None

    def subscribe(self, listener: AgentListener) -> Callable[[], None]:
        """注册 listener；注册时不会发送初始状态事件。"""

        self._listeners.append(listener)
        removed = False

        def unsubscribe() -> None:
            nonlocal removed
            if removed:
                return
            removed = True
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsubscribe

    @property
    def signal(self) -> AbortSignal | None:
        return self._signal

    def abort(self) -> None:
        if self._signal is not None:
            self._signal.abort()

    async def wait_for_idle(self) -> None:
        if self._idle_future is not None:
            await self._idle_future

    async def prompt(self, text: str) -> None:
        if self._active:
            raise RuntimeError(
                "Agent is already processing a prompt. Use a queue or wait for completion."
            )

        loop = asyncio.get_running_loop()
        # active、signal 和 idle future 共同描述一次运行的生命周期。
        self._active = True
        self._signal = AbortSignal()
        self._idle_future = loop.create_future()
        self.state.is_streaming = True
        self.state.streaming_message = None
        self.state.error_message = None

        try:
            await self._runner(text, self._process_event, self._signal)
        except Exception as error:
            await self._handle_run_failure(error, self._signal.aborted)
        finally:
            self._finish_run()

    async def _handle_run_failure(self, error: Exception, aborted: bool) -> None:
        # 失败也要走正常的 message/turn/agent 事件序列，订阅者才能统一收尾。
        failure = AssistantMessage(
            text="",
            stop_reason="aborted" if aborted else "error",
            error_message=str(error),
        )
        await self._process_event(AgentEvent("message_start", message=failure))
        await self._process_event(AgentEvent("message_end", message=failure))
        await self._process_event(AgentEvent("turn_end", message=failure))
        await self._process_event(AgentEvent("agent_end", messages=(failure,)))

    def _finish_run(self) -> None:
        # 只有所有 agent_end listener 返回后才清理运行态，随后 wait_for_idle 才会完成。
        self.state.is_streaming = False
        self.state.streaming_message = None
        self.state.pending_tool_calls.clear()
        self._active = False
        if self._idle_future is not None and not self._idle_future.done():
            self._idle_future.set_result(None)
        self._idle_future = None
        self._signal = None

    async def _process_event(self, event: AgentEvent) -> None:
        """先归约状态，再执行 listener；listener 的异步等待属于本次运行结算的一部分。"""

        if event.type in {"message_start", "message_update"}:
            self.state.streaming_message = event.message
        elif event.type == "message_end":
            self.state.streaming_message = None
            if event.message is not None:
                self.state.messages.append(event.message)
        elif event.type == "tool_execution_start":
            if event.tool_call_id is not None:
                self.state.pending_tool_calls.add(event.tool_call_id)
        elif event.type == "tool_execution_end":
            if event.tool_call_id is not None:
                self.state.pending_tool_calls.discard(event.tool_call_id)
        elif event.type == "turn_end":
            if isinstance(event.message, AssistantMessage) and event.message.error_message:
                self.state.error_message = event.message.error_message
        elif event.type == "agent_end":
            self.state.streaming_message = None

        signal = self._signal
        if signal is None:
            raise RuntimeError("Agent listener invoked outside active run")
        # 状态先归约、监听器后执行；监听器看到的是事件发生后的状态。
        for listener in tuple(self._listeners):
            result = listener(event, signal)
            if inspect.isawaitable(result):
                await result


class ScriptedRunner:
    """像低层 loop 一样发送一组固定事件。"""

    def __init__(self, events: Sequence[AgentEvent], *, delay: float = 0.0):
        self.events = tuple(events)
        self.delay = delay

    async def __call__(self, _prompt: str, emit: EventSink, signal: AbortSignal) -> None:
        for event in self.events:
            if signal.aborted:
                raise RuntimeError("run aborted")
            await emit(event)
            if self.delay:
                await asyncio.sleep(self.delay)


def demo_events(prompt: str) -> tuple[AgentEvent, ...]:
    user = UserMessage(prompt)
    partial = AssistantMessage("我先读取文件", "toolUse")
    first = AssistantMessage("我先读取文件", "toolUse")
    result = ToolResultMessage("call-1", "read_file", "hello from Pi")
    final = AssistantMessage("文件内容是 hello from Pi")
    transcript: tuple[Message, ...] = (user, first, result, final)
    return (
        AgentEvent("agent_start"),
        AgentEvent("turn_start"),
        AgentEvent("message_start", message=user),
        AgentEvent("message_end", message=user),
        AgentEvent("message_start", message=partial),
        AgentEvent("message_update", message=first),
        AgentEvent("message_end", message=first),
        AgentEvent("tool_execution_start", tool_call_id="call-1", tool_name="read_file"),
        AgentEvent(
            "tool_execution_update",
            tool_call_id="call-1",
            tool_name="read_file",
            partial_result="reading hello.py",
        ),
        AgentEvent("tool_execution_end", tool_call_id="call-1", tool_name="read_file"),
        AgentEvent("message_start", message=result),
        AgentEvent("message_end", message=result),
        AgentEvent("turn_end", message=first, tool_results=(result,)),
        AgentEvent("turn_start"),
        AgentEvent("message_start", message=final),
        AgentEvent("message_end", message=final),
        AgentEvent("turn_end", message=final),
        AgentEvent("agent_end", messages=transcript),
    )


async def demo() -> None:
    agent = Agent(ScriptedRunner(demo_events("hello.py")))
    observed: list[str] = []

    async def listener(event: AgentEvent, _signal: AbortSignal) -> None:
        observed.append(event.type)
        if event.type == "tool_execution_start":
            print(f"  pending during tool: {sorted(agent.state.pending_tool_calls)}")

    agent.subscribe(listener)
    await agent.prompt("hello.py")

    print("s03: Agent lifecycle and state reduction\n")
    print("Events")
    print("  " + " -> ".join(observed))
    print("\nState after idle")
    print(f"  is_streaming: {agent.state.is_streaming}")
    print(f"  pending_tool_calls: {sorted(agent.state.pending_tool_calls)}")
    print(f"  messages: {len(agent.state.messages)}")
    print(f"  final: {agent.state.messages[-1].text if agent.state.messages else ''}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
