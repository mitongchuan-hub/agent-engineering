#!/usr/bin/env python3
"""
s02_tool_registry.py - 工具注册：函数签名就是 Schema

s01 里工具定义是手写的 JSON（name/description/parameters……），
模型和函数各一份，改一个漏一个。这一章解决它：

    核心思想：「函数签名即 Schema」
    用 Python 的类型注解（type hints）+ inspect 反射，
    自动生成 Function Calling 协议需要的 JSON Schema。

    @registry.tool(description="两个整数相加")
    def add(a: int, b: int) -> int: return a + b
    # 自动生成：
    # {"type": "function", "function": {"name": "add",
    #   "parameters": {"properties": {"a": {"type": "integer"}, ...}}}}

好处（面试点）：
    1. 单一事实来源：不会出现"代码改了、说明书忘改"
    2. 加一个工具 = 写一个普通函数 + 一行装饰器
    3. 有默认值的参数自动标记为"非必填"

Usage:
    python s02_tool_registry/code.py          # 演示模式（无需 Key）
"""

import inspect
import json
import os
import sys
import typing
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 类型 -> JSON Schema 类型的映射表
_SCALAR = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _to_schema_type(t: Any) -> Dict[str, Any]:
    """把 Python 类型递归翻译成 JSON Schema 类型。"""
    origin = typing.get_origin(t)
    # Optional[str] / Union[str, None] -> 可空
    if origin is typing.Union:
        args = [a for a in typing.get_args(t) if a is not type(None)]
        schema = _to_schema_type(args[0]) if args else {"type": "string"}
        schema["nullable"] = True
        return schema
    # list[str] / List[str] / 裸 list（注意：裸 list 的 get_origin 是 None）
    if t is list or origin is list or origin is List:
        args = typing.get_args(t)
        items = _to_schema_type(args[0]) if args and args[0] is not Any else {"type": "string"}
        return {"type": "array", "items": items}
    # dict
    if t is dict or origin is dict or origin is Dict:
        return {"type": "object"}
    # 标量
    if t in _SCALAR:
        return {"type": _SCALAR[t]}
    # 未知类型兜底：按字符串处理（宁可宽松，不要让模型报错）
    return {"type": "string"}


class Tool:
    """一个可被 Agent 调用的工具：函数 + 自动生成的 schema。"""

    def __init__(self, func: Callable, name: Optional[str] = None,
                 description: Optional[str] = None, arg_desc: Optional[dict] = None):
        self.func = func
        self.name = name or func.__name__
        doc = inspect.getdoc(func) or ""
        self.description = (description or doc).strip() or func.__name__
        self.arg_desc = arg_desc or {}
        self.schema = self._build_schema()

    def _build_schema(self) -> dict:
        """★核心：从函数签名自动生成 {name, description, parameters}。"""
        try:
            hints = typing.get_type_hints(self.func)
        except Exception:
            hints = {}
        sig = inspect.signature(self.func)
        properties, required = {}, []
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls") or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            # get_type_hints 会把 from __future__ import annotations 的字符串注解
            # 解析成真实类型（inspect.signature 默认不解析，这是个经典坑）
            anno = hints.get(pname, p.annotation)
            if anno in (inspect.Parameter.empty, None):
                anno = str
            pschema = _to_schema_type(anno)
            if self.arg_desc.get(pname):
                pschema["description"] = self.arg_desc[pname]
            # 有默认值 -> 非必填，并给模型 default 提示
            if p.default is not inspect.Parameter.empty:
                if p.default is not None and not isinstance(p.default, (dict, list)):
                    pschema["default"] = p.default
            else:
                required.append(pname)
            properties[pname] = pschema
        return {"name": self.name, "description": self.description,
                "parameters": {"type": "object", "properties": properties,
                               "required": required}}

    def __call__(self, **kwargs):
        return self.func(**kwargs)


class ToolRegistry:
    """工具注册表：注册 / 导出 schema 给模型看 / 执行给模型用。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def tool(self, name: Optional[str] = None, description: Optional[str] = None,
             arg_desc: Optional[dict] = None):
        """装饰器用法：@registry.tool(description="...")"""
        def deco(func: Callable) -> Tool:
            self._tools[name or func.__name__] = Tool(func, name, description, arg_desc)
            return self._tools[name or func.__name__]
        return deco

    def schemas(self) -> List[dict]:
        """导出 OpenAI tools 协议格式的 schema 列表。"""
        return [{"type": "function", "function": t.schema} for t in self._tools.values()]

    def call(self, name: str, arguments: Any) -> str:
        """执行工具并返回字符串。异常全部兜住，返回给模型让它自愈。"""
        t = self._tools.get(name)
        if t is None:
            return f"错误：未知工具 '{name}'，可用：{sorted(self._tools)}"
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
            if not isinstance(args, dict):
                return f"错误：参数必须是 JSON 对象，收到：{arguments!r}"
            return json.dumps(t.func(**args), ensure_ascii=False, default=str)
        except TypeError as e:
            return f"工具调用参数错误：{e}。请参考工具 schema 修正参数后重试。"
        except Exception as e:
            return f"工具执行失败：{type(e).__name__}: {e}"


# ---------------------------------------------------------------- ① 定义工具（一行一个）

class DemoLLM:
    """演示模型：自动从 registry 选一个工具调用，第二轮给答案。
    模拟真实模型"读 schema 选工具"的行为，便于无 Key 演示。"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            # 演示模型"看懂"了 add 的 schema，决定调用它（参数类型照 schema 填）
            return {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "add", "arguments": '{"a": 10, "b": 5}'}}]}
        return {"role": "assistant", "content": "10 + 5 = 15", "tool_calls": None}


def run_agent(query: str, registry: ToolRegistry, llm) -> str:
    """复用 s01 的循环，只是工具来源换成 registry。"""
    messages = [{"role": "user", "content": query}]
    for step in range(1, 10):
        resp = llm.chat(messages, tools=registry.schemas())
        messages.append(resp)
        if not resp.get("tool_calls"):
            return resp.get("content")
        for tc in resp["tool_calls"]:
            name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            print(f"[agent] 第 {step} 轮：调用 {name}({args})")
            result = registry.call(name, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result[:100]})
            print(f"[agent] 第 {step} 轮：返回 {result[:50]}...")
    return "(达到上限)"


if __name__ == "__main__":
    registry = ToolRegistry()

    # 定义工具：类型注解 + 可选 arg_desc
    @registry.tool(arg_desc={"a": "第一个整数", "b": "第二个整数"})
    def add(a: int, b: int) -> int:
        """两个整数相加"""
        return a + b

    @registry.tool()
    def multiply(a: int, b: int) -> int:
        """两个整数相乘"""
        return a * b

    # 展示自动生成的 schema（面试现场也能手写出来）
    for t in registry.schemas():
        print(json.dumps(t, ensure_ascii=False, indent=1))
        print("---")

    print("\n[agent] 开始运行（演示模型）")
    answer = run_agent("计算两个数", registry, DemoLLM(registry))
    print(f"[agent] 最终回答：{answer}")

    # 顺带演示异常兜底：传错参数类型模型也能收到错误提示
    print("\n[agent] 演示参数错误兜底：")
    print("  ", registry.call("add", '{"a": "不是整数"}'))
    sys.exit(0)