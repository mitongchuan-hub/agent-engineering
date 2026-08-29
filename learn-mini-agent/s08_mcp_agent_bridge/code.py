#!/usr/bin/env python3
"""
s08_mcp_agent_bridge.py - Agent × MCP：让 Agent 动态外接工具服务器

s07 我们手写了 MCP Server（工具提供方）。这一章让 **Agent 当 MCP 客户端**：

    核心思想：Agent 的工具不一定要内置——
    通过 mcp_call_tool 这个桥接工具，运行时拉起外部 MCP Server 并调用其工具。

    好处（面试点）：
    1. 工具即插件：今天连这个服务器，明天换一个，Agent 代码零改动
    2. 权限隔离：外部工具跑在独立进程，坏了/挂了不影响 Agent 主进程
    3. 生态互操作：任何符合 MCP 规范的工具都能接入

    Agent(内置工具 + mcp_call_tool)
              │  mcp_call_tool(compute_match, {...})
              ▼
        MCPClient ──stdio──▶ MCPToolServer（子进程）
                                └─ 执行业务工具 → 结果回传

Usage:
    python s08_mcp_agent_bridge/code.py      # 演示：Agent 经 MCP 完成一次匹配评估
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from s07_mcp_server.code import MCPClient  # noqa: E402 复用 s07 的客户端

SERVER_CMD = [sys.executable, "-u", str(ROOT / "s07_mcp_server" / "code.py"), "--serve"]


# ---------------------------------------------------------------- ① 桥接工具

def mcp_call_tool(tool_name: str, arguments: dict = None) -> str:
    """通过 MCP 协议调用外部服务器上的工具。"""
    arguments = arguments or {}
    # 参数兜底：有些模型把 arguments 序列化成 JSON 字符串而不是对象，
    # 这里统一转成 dict（这是真实开发中踩过的坑，s09 展开）
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    with MCPClient(SERVER_CMD) as client:
        return client.request("tools/call", {"name": tool_name, "arguments": arguments}) \
                      ["content"][0]["text"]


# ---------------------------------------------------------------- ② 一个会"用协议"的演示模型

class DemoLLM:
    """演示模型：模拟真实 Agent 的决策——第一轮决定经 MCP 调用 compute_match。"""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "mcp_call_tool", "arguments": json.dumps({
                     "tool_name": "compute_match",
                     "arguments": {
                         "resume_text": "3 年经验，硕士，Python LLM RAG Agent LangChain",
                         "jd_text": "要求 2 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch",
                     }}, ensure_ascii=False)}}]}
        return {"role": "assistant", "content": "评估完成（结果见上），结论：强烈推荐。", "tool_calls": None}


# ---------------------------------------------------------------- ③ Agent（复用 s01 的循环骨架）

TOOLS = [{"type": "function", "function": {
    "name": "mcp_call_tool",
    "description": "通过外部 MCP 服务器调用工具",
    "parameters": {"type": "object", "properties": {
        "tool_name": {"type": "string"}, "arguments": {"type": "object"}},
        "required": ["tool_name"]}}}]


def run_agent(query: str, llm) -> str:
    messages = [{"role": "user", "content": query}]
    for step in range(1, 10):
        resp = llm.chat(messages, tools=TOOLS)
        messages.append(resp)
        if not resp.get("tool_calls"):
            return resp.get("content")
        for tc in resp["tool_calls"]:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"]) if isinstance(
                tc["function"]["arguments"], str) else tc["function"]["arguments"]
            print(f"[agent] 第 {step} 轮：{name}({args['tool_name']})")
            result = mcp_call_tool(args["tool_name"], args.get("arguments"))
            print(f"[agent] 第 {step} 轮：MCP 返回 -> 总分 "
                  f"{json.loads(result)['overall_score']}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result[:300]})
    return "(达到迭代上限)"


if __name__ == "__main__":
    print("Agent 经 MCP 协议外接工具服务器（无需 Key）\n")
    print("[agent] 可用工具：mcp_call_tool（动态连接 s07 的 MCP Server）")
    answer = run_agent("用 MCP 工具评估简历与 JD 的匹配度", DemoLLM())
    print(f"\n[agent] 最终回答：{answer}")
    print("\n[结论] Agent 的工具=可插拔服务：换一个 MCP Server 即可换一套能力。")
    print("       真实模式（配 Key）下，同样的桥接工具可以让 GPT/DeepSeek")
    print("       在与 s10 完整版相同的循环里外接任意 MCP 工具。")