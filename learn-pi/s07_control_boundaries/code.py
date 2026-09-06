#!/usr/bin/env python3
"""第 07 章：abort、error、terminate、agent_end 和 agent_settled。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

StopReason = Literal["stop", "error", "aborted", "length"]
PostAction = Literal["retry", "compaction", "continuation"]


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    stop_reason: StopReason
    error_message: str | None = None
    role: Literal["assistant"] = field(default="assistant", init=False)


Message: TypeAlias = UserMessage | AssistantMessage


@dataclass(frozen=True, slots=True)
class RunPlan:
    """描述一次低层 Agent 运行；`after` 模拟 Session 的运行后处理。"""

    response: AssistantMessage
    after: PostAction | None = None
    wait_for_abort: bool = False
    throw_error: str | None = None


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: Literal[
        "agent_start",
        "agent_end",
        "turn_start",
        "turn_end",
        "message_start",
        "message_end",
    ]
    message: Message | None = None
    messages: tuple[Message, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionEvent:
    type: Literal[
        "agent_end",
        "auto_retry_start",
        "compaction_start",
        "compaction_end",
        "continuation_start",
        "agent_settled",
    ]
    detail: str = ""


class AbortSignal:
    def __init__(self) -> None:
        self.aborted = False

    def abort(self) -> None:
        self.aborted = True


Listener: TypeAlias = Callable[[AgentEvent, AbortSignal], None | Awaitable[None]]
SessionListener: TypeAlias = Callable[[SessionEvent], None | Awaitable[None]]


@dataclass(slots=True)
class AgentState:
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    streaming_message: Message | None = None
    error_message: str | None = None


class AgentCore:
    """`packages/agent` 中有状态 Agent 外壳的最小投影。"""

    def __init__(self) -> None:
        self.state = AgentState()
        self._listeners: list[Listener] = []
        self._signal: AbortSignal | None = None
        self._active = False

    def subscribe(self, listener: Listener) -> Callable[[], None]:
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

    async def run(self, prompt: UserMessage | None, plan: RunPlan) -> tuple[Message, ...]:
        if self._active:
            raise RuntimeError("Agent is already processing")

        self._active = True
        self._signal = AbortSignal()
        # streaming 是 Core 运行态；Session 的 settled 还要等 post-run 工作。
        self.state.is_streaming = True
        self.state.streaming_message = None
        self.state.error_message = None
        run_messages: list[Message] = [prompt] if prompt is not None else []

        try:
            await self._emit(AgentEvent("agent_start"))
            await self._emit(AgentEvent("turn_start"))
            if prompt is not None:
                await self._emit(AgentEvent("message_start", message=prompt))
                await self._emit(AgentEvent("message_end", message=prompt))

            if plan.wait_for_abort:
                # abort 不直接杀掉协程，而是让当前响应以 aborted 原因正常收尾。
                while not self._signal.aborted:
                    await asyncio.sleep(0)
                response = AssistantMessage("", "aborted", "Operation aborted")
            elif plan.throw_error is not None:
                raise RuntimeError(plan.throw_error)
            else:
                response = plan.response

            run_messages.append(response)
            await self._emit(AgentEvent("message_start", message=response))
            await self._emit(AgentEvent("message_end", message=response))
            await self._emit(AgentEvent("turn_end", message=response))
            await self._emit(AgentEvent("agent_end", messages=tuple(run_messages)))
            return tuple(run_messages)
        except Exception as error:
            response = AssistantMessage("", "error", str(error))
            run_messages.append(response)
            await self._emit(AgentEvent("message_start", message=response))
            await self._emit(AgentEvent("message_end", message=response))
            await self._emit(AgentEvent("turn_end", message=response))
            await self._emit(AgentEvent("agent_end", messages=tuple(run_messages)))
            return tuple(run_messages)
        finally:
            # agent_end 监听器完成后，Core 才执行这里的运行态清理。
            self.state.is_streaming = False
            self.state.streaming_message = None
            self._active = False
            self._signal = None

    async def _emit(self, event: AgentEvent) -> None:
        if event.type == "message_start":
            self.state.streaming_message = event.message
        elif event.type == "message_end":
            self.state.streaming_message = None
            if event.message is not None:
                self.state.messages.append(event.message)
        elif event.type == "turn_end":
            if isinstance(event.message, AssistantMessage) and event.message.error_message:
                self.state.error_message = event.message.error_message
        elif event.type == "agent_end":
            self.state.streaming_message = None

        signal = self._signal
        if signal is None:
            raise RuntimeError("Agent event outside active run")
        # 先更新 state，再 await listeners；agent_end listener 完成前 Core 仍保持 active。
        for listener in tuple(self._listeners):
            result = listener(event, signal)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]


class AgentSession:
    """只有运行后处理完成后才发出 settled 的高层 Session。"""

    def __init__(self, core: AgentCore, plans: Sequence[RunPlan]):
        self.core = core
        self._plans = list(plans)
        self._listeners: list[SessionListener] = []
        self._session_events: list[SessionEvent] = []
        self._active = False
        self._idle_future: asyncio.Future[None] | None = None
        self._core_events: list[str] = []
        core.subscribe(self._observe_core_event)

    @property
    def is_idle(self) -> bool:
        return not self._active

    @property
    def events(self) -> tuple[SessionEvent, ...]:
        return tuple(self._session_events)

    def subscribe(self, listener: SessionListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsubscribe

    async def prompt(self, text: str) -> None:
        if self._active:
            raise RuntimeError("Session is already processing")
        if not self._plans:
            raise RuntimeError("No run plan")

        self._active = True
        self._idle_future = asyncio.get_running_loop().create_future()
        try:
            prompt: UserMessage | None = UserMessage(text)
            while True:
                # 每个 post-run action 都开启一次新的 Core run，但 continuation 不新增用户消息。
                plan = self._plans.pop(0)
                await self.core.run(prompt, plan)
                if plan.after is None:
                    break
                await self._post_run(plan.after)
                prompt = None
        finally:
            # agent_end 后仍可能 retry/compaction/continuation；settled 放在最外层 finally。
            await self._emit_session(SessionEvent("agent_settled"))
            self._active = False
            if self._idle_future is not None and not self._idle_future.done():
                self._idle_future.set_result(None)
            self._idle_future = None

    async def _post_run(self, action: PostAction) -> None:
        event_type: Literal["auto_retry_start", "compaction_start", "continuation_start"]
        if action == "retry":
            event_type = "auto_retry_start"
        elif action == "compaction":
            event_type = "compaction_start"
        else:
            event_type = "continuation_start"
        await self._emit_session(SessionEvent(event_type, "post agent_end"))
        if action == "compaction":
            await self._emit_session(SessionEvent("compaction_end", "recovered"))

    async def _observe_core_event(self, event: AgentEvent, _signal: AbortSignal) -> None:
        self._core_events.append(event.type)
        if event.type == "agent_end":
            await self._emit_session(SessionEvent("agent_end", "low-level run ended"))

    async def _emit_session(self, event: SessionEvent) -> None:
        self._session_events.append(event)
        for listener in tuple(self._listeners):
            result = listener(event)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]

    def abort(self) -> None:
        self.core.abort()

    async def abort_and_wait(self) -> None:
        self.abort()
        await self.wait_for_idle()

    async def wait_for_idle(self) -> None:
        if self._idle_future is not None:
            await self._idle_future


def _show_event(event: SessionEvent) -> str:
    return event.type + (f" ({event.detail})" if event.detail else "")


async def demo() -> None:
    core = AgentCore()
    session = AgentSession(
        core,
        [
            RunPlan(AssistantMessage("temporary failure", "error", "timeout"), after="retry"),
            RunPlan(AssistantMessage("recovered", "stop")),
        ],
    )
    await session.prompt("do work")

    print("s07: control boundaries\n")
    print("Session events")
    for event in session.events:
        print(f"  {_show_event(event)}")
    print("\nState after settled")
    print(f"  core.is_streaming: {core.state.is_streaming}")
    print(f"  session.is_idle: {session.is_idle}")
    print(f"  final response: {core.state.messages[-1].text}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
