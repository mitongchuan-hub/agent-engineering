"""第 12 章：综合 Coding Agent 的消息模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias


StopReason = Literal["stop", "toolUse", "length", "error", "aborted"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UserMessage:
    content: str
    role: Literal["user"] = field(default="user", init=False)


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: StopReason = "stop"
    error_message: str | None = None
    role: Literal["assistant"] = field(default="assistant", init=False)


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    role: Literal["toolResult"] = field(default="toolResult", init=False)


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    content: str
    role: Literal["notification"] = field(default="notification", init=False)


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage | NotificationMessage


def message_to_dict(message: Message) -> dict[str, Any]:
    if isinstance(message, UserMessage):
        return {"role": message.role, "content": message.content}
    if isinstance(message, NotificationMessage):
        return {"role": message.role, "content": message.content}
    if isinstance(message, ToolResultMessage):
        return {
            "role": message.role,
            "toolCallId": message.tool_call_id,
            "toolName": message.tool_name,
            "content": message.content,
            "isError": message.is_error,
        }
    return {
        "role": message.role,
        "content": message.content,
        "toolCalls": [
            {"id": call.id, "name": call.name, "arguments": call.arguments}
            for call in message.tool_calls
        ],
        "stopReason": message.stop_reason,
        "errorMessage": message.error_message,
    }


def message_from_dict(raw: dict[str, Any]) -> Message:
    role = raw.get("role")
    if role == "user":
        return UserMessage(str(raw.get("content", "")))
    if role == "notification":
        return NotificationMessage(str(raw.get("content", "")))
    if role == "toolResult":
        return ToolResultMessage(
            str(raw.get("toolCallId", "")),
            str(raw.get("toolName", "")),
            str(raw.get("content", "")),
            bool(raw.get("isError", False)),
        )
    if role == "assistant":
        calls = tuple(
            ToolCall(str(item["id"]), str(item["name"]), dict(item.get("arguments", {})))
            for item in raw.get("toolCalls", [])
        )
        return AssistantMessage(
            str(raw.get("content", "")),
            calls,
            raw.get("stopReason", "stop"),
            raw.get("errorMessage"),
        )
    raise ValueError(f"未知消息角色: {role}")
