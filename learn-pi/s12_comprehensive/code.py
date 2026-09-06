#!/usr/bin/env python3
"""第 12 章：把前 11 章组合成完整的离线 Coding Agent。"""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil

if __package__:
    from .agent import ComprehensiveAgent
    from .context import ContextPolicy
    from .extensions import ExtensionAPI, load_extensions
    from .models import AssistantMessage, ToolCall
    from .provider import ScriptedProvider
    from .recovery import RecoveryPolicy
    from .session import SessionStore
    from .tools import ToolDefinition, ToolRegistry
else:
    # 允许从仓库根目录直接执行本文件。
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from s12_comprehensive.agent import ComprehensiveAgent
    from s12_comprehensive.context import ContextPolicy
    from s12_comprehensive.extensions import ExtensionAPI, load_extensions
    from s12_comprehensive.models import AssistantMessage, ToolCall
    from s12_comprehensive.provider import ScriptedProvider
    from s12_comprehensive.recovery import RecoveryPolicy
    from s12_comprehensive.session import SessionStore
    from s12_comprehensive.tools import ToolDefinition, ToolRegistry


async def demo() -> None:
    output_dir = Path(".task-output/s12-demo")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    session = SessionStore.create("learn-pi-demo", output_dir / "session.jsonl")
    registry = ToolRegistry()

    def extension(api: ExtensionAPI) -> None:
        # 扩展只注册工具；它不需要知道 Agent Loop 如何调度工具。
        api.register_tool(
            ToolDefinition(
                "read_memory_file",
                "读取一个内存文件",
                lambda arguments: f"内容: {arguments.get('path', 'hello.txt')} -> hello from Pi",
            )
        )

    load_extensions(registry, [extension])
    provider = ScriptedProvider(
        [
            AssistantMessage(
                "我先读取文件。",
                (ToolCall("call-1", "read_memory_file", {"path": "hello.txt"}),),
                "toolUse",
            ),
            AssistantMessage("文件内容是 hello from Pi。", stop_reason="stop"),
        ]
    )
    agent = ComprehensiveAgent(
        provider,
        registry,
        session,
        context_policy=ContextPolicy(keep_recent=12),
        recovery_policy=RecoveryPolicy(max_context_messages=12, keep_recent_messages=6),
    )
    result = await agent.prompt("hello.txt 里有什么？")

    print("s12: comprehensive offline coding agent\n")
    print("events:")
    print("  " + " -> ".join(event.type for event in result.events))
    print(f"provider calls: {len(result.requests)}")
    print(f"session entries: {len(session.get_entries())}")
    print(f"context messages: {[getattr(message, 'content', '') for message in result.messages]}")
    print(f"session file: {session.path}")


def main() -> int:
    asyncio.run(demo())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
