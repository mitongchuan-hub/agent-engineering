"""MCP 演示：两档模式任选。

    python demo_mcp.py --cli      # 纯协议演示（无需 key）：握手 -> 列工具 -> 调 compute_match
    python demo_mcp.py            # Agent 演示（需要 key）：Agent 通过 mcp_call_tool 动态调用外部 MCP 服务器

运行效果（cli 模式）会让你直观看到 MCP 的三步生命周期。
"""
from __future__ import annotations

import json
import sys

import app.main as appmod
import config as cfg
from app.mcp_tools import register_mcp_bridge
from app.mcp_server import build_server  # noqa: F401  # 确保路径正确（提示）
from mini_agent.tools import ToolRegistry

SERVER_CMD = [sys.executable, "-u", str(appmod.BASE_DIR / "mcp_server.py")]


def demo_cli():
    """不依赖 LLM：直接用 MCPClient 跑协议。"""
    print("=== MCP 协议演示（纯客户端，无 LLM）===")
    from mini_agent.mcp import MCPClient
    with MCPClient(SERVER_CMD, cwd=str(appmod.BASE_DIR.parent)) as client:
        print("① initialize + notifications/initialized   ✅ 握手完成")
        tools = client.list_tools()
        print(f"② tools/list：{len(tools)} 个工具 -> {[t['name'] for t in tools]}")
        out = client.call_tool("compute_match", {
            "resume_text": "3 年硕士 Python LLM RAG Agent 后端",
            "jd_text": "2 年以上 硕士 Python LLM RAG Agent",
        })
        r = json.loads(out)
        print(f"③ tools/call compute_match -> 总分 {r['overall_score']}，结论「{r['verdict']}」")
        print(f"   维度分数：{r['dim_scores']}")
    print("=== 协议演示结束 ===")


def demo_agent():
    """Agent 通过 mcp_call_tool 连接外部 MCP 服务器完成任务。"""
    registry = ToolRegistry()
    from app.tools import register_domain_tools
    register_domain_tools(registry)                    # 内置工具
    register_mcp_bridge(registry, SERVER_CMD,          # + MCP 外接工具
                        server_cwd=str(appmod.BASE_DIR.parent))
    from mini_agent.llm import ChatClient
    from mini_agent.agent import Agent
    llm = ChatClient(base_url=cfg.LLM_BASE_URL, api_key=cfg.LLM_API_KEY,
                     model=cfg.LLM_MODEL, temperature=cfg.TEMPERATURE,
                     extra_body=cfg.EXTRA_LLM_PARAMS)
    agent = Agent(llm=llm, registry=registry,
                  system_prompt=(
                      "你是资深 HR 招聘顾问。本次任务要求优先通过 mcp_call_tool 工具"
                      "（连接外部 MCP 服务器）完成评估：先用 mcp_call_tool 调用 "
                      "read_text_file 读取 JD，再调用 compute_match 打分。"
                      "基于真实返回数据给出结论。"
                  ), max_iters=8)

    task = ("请用 MCP 工具评估 app/data/sample_resume.md 对 app/data/jds/ai_engineer.md "
            "的匹配度，给出总分与结论、缺口技能。")
    answer = agent.run(task)
    print("\n================ 最终回答 ================")
    print(answer)


if __name__ == "__main__":
    if "--cli" in sys.argv or cfg.MOCK_MODE:
        demo_cli()
    else:
        demo_agent()