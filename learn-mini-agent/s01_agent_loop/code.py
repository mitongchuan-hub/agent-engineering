#!/usr/bin/env python3
"""
s01_agent_loop.py - Agent 核心循环（一个 while 就够）

AI 编程 Agent 的核心机密，其实就是一个循环：
    while 模型还要调用工具:
        1. 把「历史消息 + 工具定义」发给 LLM
        2. LLM 要么给最终回答，要么请求调用工具（tool_calls）
        3. 若是工具调用：执行工具 -> 结果作为 tool 消息回填 -> 回到 1
        4. 若不再调用工具：输出最终回答，循环结束

    +------+      +------+      +-------------+
    | User | ---> | LLM  | ---> |   exec tool |
    |  msg |      |      |      |   result    |
    +------+      +--+---+      +------+------+
                     ^                  |
                     |  tool result     |
                     +------------------+
                     (循环继续)

核心思想：把工具执行结果「重新喂回」模型，直到模型自己决定不再调用工具。
这一步先不接真实模型，用一个"脚本化演示模型"看清循环骨架；
下一步（s02）再加工具注册，再下一步（s03）才接真实 LLM。

Usage:
    python s01_agent_loop/code.py            # 演示模式（无需 Key）
    LLM_API_KEY=sk-xxx python s01_agent_loop/code.py   # 真实模型（可选）
"""

import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------- ① 配置

def load_env(path: str = ".env") -> None:
    """迷你 .env 加载器（避免额外依赖 python-dotenv）。"""
    p = Path(__file__).resolve().parent.parent / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k:
                os.environ.setdefault(k, v)


load_env()


# ---------------------------------------------------------------- ② 工具

def add(a: int, b: int) -> int:
    """加法工具：演示 Agent 循环里被调用的最小工具。"""
    return a + b


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "两个整数相加",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        },
    }
]


def call_tool(name: str, arguments: str) -> str:
    """执行工具。参数解析失败/执行异常都以字符串返回，绝不抛死。"""
    try:
        args = json.loads(arguments)
        if name == "add":
            return str(add(args["a"], args["b"]))
        return f"未知工具: {name}"
    except Exception as e:
        return f"工具调用出错: {e}"


# ---------------------------------------------------------------- ③ 模型：演示模式 or 真实

class FakeLLM:
    """脚本化演示模型：第一轮请求调用 add，拿到结果后再给最终答案。

    用它可以在没有 Key 的情况下，观察 Agent 循环的完整行为：
    第 1 轮 -> tool_calls(add)  第 2 轮 -> 最终回答
    """

    def __init__(self, user_q: str):
        self.calls = 0
        self.user_q = user_q

    def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "call_1", "type": "function",
                     "function": {"name": "add", "arguments": '{"a": 2, "b": 3}'}},
                ],
            }
        return {"role": "assistant", "content": f"答案是 5。", "tool_calls": None}


def get_llm():
    if os.getenv("LLM_API_KEY") and not os.getenv("LLM_API_KEY", "").startswith("sk-your"):
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/") + "/v1" if not os.getenv("LLM_BASE_URL", "").endswith("/v1") else os.getenv("LLM_BASE_URL"),
                api_key=os.getenv("LLM_API_KEY"),
            )
            return client
        except ImportError:
            pass
    return None


# ---------------------------------------------------------------- ④ Agent 核心循环

def run_agent(query: str, llm, verbose: bool = True) -> str:
    """Agent 主循环。

    面试就背这一段伪代码：
        repeat:
            resp = LLM(messages, tools)
            messages.append(resp)
            if resp 没有 tool_calls:   return 最终回答
            for tc in resp.tool_calls:
                result = call_tool(tc.name, tc.args)
                messages.append({"role": "tool", content: result})
    """
    messages = [{"role": "user", "content": query}]
    max_iters = 20  # 安全上限：防止模型陷入死循环烧钱
    if verbose:
        print(f"[agent] 任务：{query}")

    for step in range(1, max_iters + 1):
        # 第 1 步：把「消息 + 工具定义」发给模型
        if isinstance(llm, FakeLLM):
            resp = llm.chat(messages, tools=TOOLS)
        else:  # 真实 OpenAI 兼容客户端
            kwargs = {"model": os.getenv("LLM_MODEL", "deepseek-chat"),
                      "messages": messages, "tools": TOOLS, "temperature": 0.3}
            msg = llm.chat.completions.create(**kwargs).choices[0].message
            resp = {
                "role": "assistant", "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "function": {"name": tc.function.name,
                                               "arguments": tc.function.arguments}}
                    for tc in (msg.tool_calls or [])
                ] or None,
            }
        messages.append(resp)

        tool_calls = resp.get("tool_calls")
        if not tool_calls:  # 模型说"我做完了"
            if verbose:
                print(f"[agent] 第 {step} 轮：无工具调用，循环结束")
            return resp.get("content") or "(空回复)"

        # 第 2 步：执行所有被请求的工具
        for tc in tool_calls:
            name = tc["function"]["name"]
            raw_args = tc["function"]["arguments"]
            if verbose:
                print(f"[agent] 第 {step} 轮：调用工具 {name}({raw_args})")
            result = call_tool(name, raw_args)
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": result})
            if verbose:
                print(f"[agent] 第 {step} 轮：{name} 返回 {result}")

    return "(达到迭代上限)"  # 防御：正常情况下不会走到这


# ---------------------------------------------------------------- ⑤ 演示

if __name__ == "__main__":
    real = get_llm()
    if real:
        print("使用真实模型（已配置 LLM_API_KEY）")
        answer = run_agent("帮我算一下 2+3", llm=real)
    else:
        print("演示模式：内置脚本化模型观察循环（配 Key 可走真实大模型）")
        answer = run_agent("帮我算一下 2+3", llm=FakeLLM("帮我算一下 2+3"))

    print("\n================ 最终回答 ================")
    print(answer)
    print("==========================================")
    sys.exit(0)