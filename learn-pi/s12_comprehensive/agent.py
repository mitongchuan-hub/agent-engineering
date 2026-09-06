"""第 12 章：综合 Agent 编排器。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .context import ContextPolicy, ContextSnapshot
from .models import AssistantMessage, Message, ToolResultMessage, UserMessage
from .provider import ModelRequest, Provider
from .recovery import CompactionRecord, RecoveryPolicy
from .session import SessionStore
from .tools import ToolBatch, ToolRegistry


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    messages: tuple[Message, ...]
    requests: tuple[ModelRequest, ...]
    context_snapshots: tuple[ContextSnapshot, ...]
    events: tuple[AgentEvent, ...]


class ComprehensiveAgent:
    """将前面系统按边界组合起来的最小 Agent。"""

    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        session: SessionStore,
        *,
        context_policy: ContextPolicy | None = None,
        recovery_policy: RecoveryPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.session = session
        self.context_policy = context_policy or ContextPolicy()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.system_prompt = "You are a coding agent."
        self.is_streaming = False
        self._excluded_entry_ids: set[str] = set()

    async def prompt(self, text: str) -> AgentRunResult:
        if self.is_streaming:
            raise RuntimeError("Agent 已经在运行")

        self.is_streaming = True
        events: list[AgentEvent] = [AgentEvent("agent_start")]
        snapshots: list[ContextSnapshot] = []
        self.session.append_message(UserMessage(text))
        events.extend([AgentEvent("turn_start"), AgentEvent("user_message", text)])

        try:
            while True:
                # 普通阈值压缩发生在下一次 Provider 请求之前。
                compaction = self.recovery_policy.compact_if_needed(
                    self.session,
                    excluded_entry_ids=self._excluded_entry_ids,
                )
                if compaction is not None:
                    self._record_compaction(compaction, events, reason="threshold")

                context_messages = self.session.context_messages(self._excluded_entry_ids)
                snapshot = self.context_policy.build(context_messages)
                snapshots.append(snapshot)
                events.append(AgentEvent("provider_request", str(len(snapshot.messages))))
                response = await self.provider.complete(
                    ModelRequest(snapshot.messages, self.tools.names())
                )
                response_entry_id = self.session.append_message(response)
                events.append(AgentEvent("assistant_message", response.stop_reason))

                if response.stop_reason in {"error", "aborted"}:
                    events.append(AgentEvent("agent_end", response.stop_reason))
                    break

                if response.stop_reason == "length":
                    compaction = self.recovery_policy.handle_length_stop(
                        self.session,
                        response_entry_id,
                    )
                    if compaction is None:
                        events.append(AgentEvent("overflow_recovery_failed"))
                        events.append(AgentEvent("agent_end", "length"))
                        break
                    self._excluded_entry_ids.add(response_entry_id)
                    self._record_compaction(compaction, events, reason="overflow")
                    events.append(AgentEvent("overflow_retry"))
                    continue

                if response.tool_calls:
                    events.append(AgentEvent("tool_batch_start", str(len(response.tool_calls))))
                    batch = await self.tools.execute_batch(response.tool_calls)
                    self._append_tool_results(batch, events)
                    if batch.terminated:
                        events.append(AgentEvent("agent_end", "tool_terminate"))
                        break
                    continue

                events.append(AgentEvent("agent_end", "stop"))
                break
        except Exception as error:
            failed = AssistantMessage("", stop_reason="error", error_message=str(error))
            self.session.append_message(failed)
            events.extend([AgentEvent("agent_end", "error"), AgentEvent("error", str(error))])
        finally:
            # 综合章把 Session 的最终稳定边界显式暴露出来。
            events.append(AgentEvent("agent_settled"))
            self.is_streaming = False

        return AgentRunResult(
            messages=self.session.context_messages(self._excluded_entry_ids),
            requests=tuple(getattr(self.provider, "requests", [])),
            context_snapshots=tuple(snapshots),
            events=tuple(events),
        )

    @staticmethod
    def _record_compaction(compaction: CompactionRecord, events: list[AgentEvent], *, reason: str) -> None:
        events.extend(
            [
                AgentEvent("compaction_start", reason),
                AgentEvent("compaction_end", compaction.first_kept_entry_id),
            ]
        )

    def _append_tool_results(self, batch: ToolBatch, events: list[AgentEvent]) -> None:
        for result in batch.results:
            self.session.append_message(
                ToolResultMessage(
                    result.tool_call_id,
                    result.tool_name,
                    result.content,
                    result.is_error,
                )
            )
            events.append(AgentEvent("tool_result", result.tool_call_id))
