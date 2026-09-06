"""第 12 章：综合 Agent 的扩展 API。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .tools import ToolDefinition, ToolRegistry


@dataclass(frozen=True, slots=True)
class ExtensionEvent:
    name: str
    detail: str = ""


class ExtensionAPI:
    """综合章只保留工具注册和事件记录两个扩展入口。"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.events: list[ExtensionEvent] = []
        self._session_start_handlers: list[Callable[[], None]] = []

    def register_tool(self, tool: ToolDefinition) -> None:
        self.registry.register(tool)

    def on_session_start(self, handler: Callable[[], None]) -> None:
        self._session_start_handlers.append(handler)

    def emit_session_start(self) -> None:
        self.events.append(ExtensionEvent("session_start"))
        for handler in tuple(self._session_start_handlers):
            handler()


def load_extensions(registry: ToolRegistry, factories: list[Callable[[ExtensionAPI], None]]) -> ExtensionAPI:
    """按顺序加载扩展；扩展负责注册，Agent 负责消费注册结果。"""

    api = ExtensionAPI(registry)
    for factory in factories:
        factory(api)
    api.emit_session_start()
    return api
