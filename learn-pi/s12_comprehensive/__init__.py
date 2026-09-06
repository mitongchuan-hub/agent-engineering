"""第 12 章：综合 Coding Agent。"""

from .agent import AgentEvent, AgentRunResult, ComprehensiveAgent
from .context import ContextPolicy, ContextSnapshot
from .extensions import ExtensionAPI, ExtensionEvent, load_extensions
from .models import (
    AssistantMessage,
    Message,
    NotificationMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    message_from_dict,
    message_to_dict,
)
from .provider import ModelRequest, Provider, ScriptedProvider
from .recovery import CompactionRecord, RecoveryPolicy
from .session import SessionEntry, SessionStore
from .tools import ToolBatch, ToolDefinition, ToolRegistry

__all__ = [
    "AgentEvent",
    "AgentRunResult",
    "AssistantMessage",
    "CompactionRecord",
    "ComprehensiveAgent",
    "ContextPolicy",
    "ContextSnapshot",
    "ExtensionAPI",
    "ExtensionEvent",
    "Message",
    "ModelRequest",
    "NotificationMessage",
    "Provider",
    "RecoveryPolicy",
    "ScriptedProvider",
    "SessionEntry",
    "SessionStore",
    "ToolBatch",
    "ToolCall",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResultMessage",
    "UserMessage",
    "load_extensions",
    "message_from_dict",
    "message_to_dict",
]
