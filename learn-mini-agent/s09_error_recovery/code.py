#!/usr/bin/env python3
"""
s09_error_recovery.py - 健壮性：让 Agent 在真实世界里"摔不坏"

教学版本里一切顺利；真实生产里模型什么都会干：
- 把 arguments 传成 JSON 字符串而不是对象
- 参数类型传错、缺字段
- 工具执行抛异常
- 陷入循环不结束

这一章的四个防线（每个都是真实踩过的坑）：

    ① 参数兜底  ：arguments 可能是字符串，统一 _coerce_args
    ② 结果截断  ：超长工具输出截断，防止撑爆上下文
    ③ 错误回传  ：工具异常变成字符串回传模型，让它自愈重试
    ④ 迭代上限  ：max_iters 兜底，防模型死循环烧钱

Usage:
    python s09_error_recovery/code.py     # 演示四个防线 + 一个"自愈"故事
"""

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------- ① 防线：参数兜底

def _coerce_args(arguments) -> Dict[str, Any]:
    """部分模型把 arguments 序列化成 JSON 字符串而非对象，统一转 dict。

    真实案例：gpt-5.5 调 mcp_call_tool 时传了
        "arguments": "{\"path\":\"...\"}"
    而不是 {"path": "..."}，服务端 **args 当场 TypeError。
    桥接层做一次归一，Agent 稳如老狗。
    """
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        return json.loads(arguments)          # "{\"a\":1}" -> {"a":1}
    if isinstance(arguments, dict):
        return arguments
    return {}


# ---------------------------------------------------------------- ② 防线：结果截断

MAX_TOOL_RESULT = 200  # 字符

def _truncate(text: str) -> str:
    """超长工具输出截断：防上下文爆掉（s04 的预算之外的另一道闸）。"""
    return text if len(text) <= MAX_TOOL_RESULT else text[:MAX_TOOL_RESULT] + f"...(截断,共{len(text)}字符)"


# ---------------------------------------------------------------- ③ 防线：错误回传（执行器）

class Executor:
    """工具执行器：无论发生什么，都返回字符串给模型（绝不崩整个 Agent）。"""

    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._register()

    def _register(self):
        def get_weather(city: str) -> dict:
            return {"city": city, "temp": 25, "desc": "晴"}
        def risky_div(a: int, b: int) -> float:
            return a / b            # b=0 会抛 ZeroDivisionError
        self._tools = {"get_weather": get_weather, "risky_div": risky_div}

    def call(self, name: str, arguments: Any) -> str:
        func = self._tools.get(name)
        if func is None:
            return f"错误：未知工具 '{name}'，可用：{sorted(self._tools)}"
        try:
            args = _coerce_args(arguments)                     # ①
            return _truncate(json.dumps(func(**args), ensure_ascii=False, default=str))  # ②
        except TypeError as e:
            # 参数错：告诉模型怎么改，让它重试（③ 自愈入口）
            return f"工具调用参数错误：{e}。请参考工具 schema 修正参数后重试。"
        except Exception as e:
            return f"工具执行失败：{type(e).__name__}: {e}\n{traceback.format_exc(limit=2)}"


# ---------------------------------------------------------------- 演示

class NaiveModel:
    """一个"会犯错"的模型：三个场景逐个演示。"""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        q = messages[0]["content"]
        if q.startswith("场景A"):      # A: 参数是字符串 -> ① 兜底后一次成功
            if any(m.get("role") == "tool" for m in messages):
                return {"role": "assistant", "content": "天气查询成功（字符串参数已被 _coerce_args 归一为对象）", "tool_calls": None}
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "a1", "type": "function",
                 "function": {"name": "get_weather",
                              "arguments": '{"city": "北京"}'}}]}   # 协议层 arguments 永远是 JSON 字符串
        if q.startswith("场景B"):      # B: 除零异常 -> ③ 错误回传 + 自愈
            self.calls += 0
            if messages[-1].get("role") == "tool":
                return {"role": "assistant", "content": "b=0 不行，那我改用 b=2：a=10/2=5。", "tool_calls": None}
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "b1", "type": "function",
                 "function": {"name": "risky_div", "arguments": '{"a": 10, "b": 0}'}}]}
        if q.startswith("场景C"):      # C: 永远调工具 -> ④ 迭代上限兜底
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "get_weather", "arguments": '{"city": "上海"}'}}]}
        return {"role": "assistant", "content": "完成", "tool_calls": None}


def run_agent(query: str, llm, executor: Executor, max_iters: int = 3) -> str:
    messages = [{"role": "user", "content": query}]
    for step in range(1, max_iters + 1):
        resp = llm.chat(messages)
        messages.append(resp)
        if not resp.get("tool_calls"):
            return resp.get("content")
        for tc in resp["tool_calls"]:
            out = executor.call(tc["function"]["name"], tc["function"]["arguments"])
            print(f"    [step {step}] 工具返回 -> {out[:70]}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
    return "(到达迭代上限，强制收尾——防线④生效)"


if __name__ == "__main__":
    ex = Executor()
    model = NaiveModel()

    print("场景A｜模型把 arguments 传成 JSON 字符串 -> ① 参数兜底")
    print("   ", run_agent("场景A 查询天气", model, ex))

    print("\n场景B｜工具抛 ZeroDivisionError -> ③ 错误回传 -> 模型自愈")
    print("   ", run_agent("场景B 计算 10/0", model, ex))

    print("\n场景C｜模型永远调工具 -> ④ 迭代上限兜底")
    print("   ", run_agent("场景C forever", model, ex, max_iters=3))

    print("\n[结论] Agent 的健壮性不是运气，是把每个失败都变成数据流的一部分：")
    print("        字符串兜底 + 截断 + 错误回传 + 迭代上限 = 摔不坏的最小骨架")