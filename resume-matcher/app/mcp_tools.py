"""MCP 桥接工具：让我们的 Agent 在运行时动态连接外部 MCP 服务器。

面试点：把「Agent 的工具」抽象成「可插拔的外部服务」——同一个 Agent，
今天连这个 MCP server，明天换一个，代码零改动。这是 MCP 生态的价值核心。
"""
from __future__ import annotations

import json
from typing import Optional

from mini_agent.mcp import MCPClient
from mini_agent.tools import ToolRegistry


def _coerce_args(arguments) -> dict:
    """健壮性：部分模型会把 arguments 序列化成 JSON 字符串而非对象，这里统一成 dict。
    真实教训：function calling 的 arguments 字段在不同模型间飘忽不定，
    调用方必须做类型兜底（这也是评测集存在的意义之一）。"""
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        return json.loads(arguments)
    if isinstance(arguments, dict):
        return arguments
    return {}


def register_mcp_bridge(registry: ToolRegistry, server_cmd: list,
                        server_cwd: Optional[str] = None) -> ToolRegistry:
    """注册一个 mcp_call_tool 工具：参数是 (tool_name, arguments)，
    通过 MCP 协议把请求转发给 server_cmd 启动的进程。"""

    def mcp_call_tool(tool_name: str, arguments: dict = None) -> str:
        with MCPClient(server_cmd, cwd=server_cwd) as client:
            return client.call_tool(tool_name, _coerce_args(arguments))

    registry.tool(
        name="mcp_call_tool",
        description=(
            "通过外部 MCP 服务器调用工具（动态连接，支持任意已注册的 MCP 工具）。"
            "参数 tool_name 是 MCP 工具名，arguments 是传给该工具的 JSON 对象。"
            "当前可用 MCP 工具会随调用结果或模型能力而定，先用 compute_match 等"
        ),
        arg_desc={"tool_name": "MCP 工具名，如 compute_match / read_text_file",
                  "arguments": "传给该 MCP 工具的参数 JSON 对象"},
    )(mcp_call_tool)
    return registry