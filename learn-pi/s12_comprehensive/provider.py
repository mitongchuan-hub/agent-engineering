"""第 12 章：Provider 边界。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from .models import AssistantMessage, Message


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: tuple[Message, ...]
    tool_names: tuple[str, ...]


class Provider(Protocol):
    async def complete(self, request: ModelRequest) -> AssistantMessage:
        """根据当前模型上下文返回一条 assistant 消息。"""


@dataclass(slots=True)
class ScriptedProvider:
    """离线 Provider：按顺序返回预设响应，并记录模型请求。"""

    responses: Sequence[AssistantMessage]
    requests: list[ModelRequest] = field(default_factory=list)
    _index: int = 0

    async def complete(self, request: ModelRequest) -> AssistantMessage:
        self.requests.append(request)
        if self._index >= len(self.responses):
            raise RuntimeError("ScriptedProvider 没有剩余响应")
        response = self.responses[self._index]
        self._index += 1
        return response
