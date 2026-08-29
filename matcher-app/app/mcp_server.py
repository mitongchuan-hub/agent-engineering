"""MCP Server 入口：把应用层工具（compute_match / read_text_file）暴露为 MCP 工具。

运行（单独给任意 MCP 客户端做服务）：
    python app/mcp_server.py

复用 mini_agent 的 schema 自动生成：Tool(func).schema["parameters"] 就是 MCP 的
inputSchema —— 一套签名，OpenAI function calling 和 MCP 两种协议通吃。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 被外部以「脚本方式」拉起时（python app/mcp_server.py），sys.path 只有 app/，
# 这里把项目根目录补回去，保证 mini_agent 可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mini_agent.mcp import MCPToolServer
from mini_agent.tools import Tool
from app.tools import compute_match, read_text_file


def build_server() -> MCPToolServer:
    server = MCPToolServer(name="matcher-app", version="1.0.0")
    for func in (compute_match, read_text_file):
        t = Tool(func)  # 复用函数签名 → JSON Schema 自动生成
        server.add_tool(name=t.name, description=t.description,
                        input_schema=t.schema["parameters"], handler=t.func)
    return server


if __name__ == "__main__":
    build_server().run_stdio()