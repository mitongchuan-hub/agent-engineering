"""第 12 章：综合 Agent 的上下文策略。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import AssistantMessage, Message, NotificationMessage, ToolResultMessage, UserMessage


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    transcript_count: int
    model_message_count: int
    messages: tuple[Message, ...]


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """把完整 transcript 裁剪成当前模型请求的只读快照。"""

    keep_recent: int | None = None

    def transform(self, messages: Sequence[Message]) -> list[Message]:
        selected = list(messages)
        if self.keep_recent is not None:
            selected = selected[-max(0, self.keep_recent) :]
        return selected

    def convert_to_llm(self, messages: Sequence[Message]) -> list[Message]:
        return [message for message in messages if not isinstance(message, NotificationMessage)]

    def build(self, messages: Sequence[Message]) -> ContextSnapshot:
        transformed = self.transform(messages)
        converted = self.convert_to_llm(transformed)
        return ContextSnapshot(len(messages), len(converted), tuple(converted))
