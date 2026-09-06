"""Chapter 2 package: Provider event streams and partial responses."""

from .code import (
    AssistantMessage,
    AssistantMessageEventStream,
    AssistantStreamEvent,
    AssembledResponse,
    EventStream,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    assemble_assistant_response,
    scripted_text_stream,
)

__all__ = [
    "AssistantMessage",
    "AssistantMessageEventStream",
    "AssistantStreamEvent",
    "AssembledResponse",
    "EventStream",
    "TextBlock",
    "ThinkingBlock",
    "ToolCallBlock",
    "assemble_assistant_response",
    "scripted_text_stream",
]
