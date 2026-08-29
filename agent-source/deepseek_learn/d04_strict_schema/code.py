#!/usr/bin/env python3
"""
d04_strict_schema.py - deepseek_learn 第 4 步：严格工具 schema

deepseek 的 tools 包比很多框架严谨：ptc.ts / py-types.ts / ts-types.ts
能对参数做多语言、多类型推导——工具定义不是"描述个大概"，而是**可校验的合同**。

本步重建教学版：
    ① 从 Python 类型注解生成 JSON Schema（复用 learn-mini-agent s02）
    ② 加一个"运行时校验器"：模型给的参数不合法 → 拒绝执行 → 回传原因
    ③ 支持字面量约束（enum）、嵌套对象、可选字段

面试点：schema 不只是"给模型看"，还是"执行的守门员"——
模型幻觉参数（类型错/枚举错）在守门员这里被拦下，而不是打进函数。

Usage:
    python d04_strict_schema/code.py
"""

import inspect
import json
import typing
from typing import Any, Callable, Dict, List, Optional

_SCALAR = {str: "string", int: "integer", float: "number", bool: "boolean"}


def to_schema(t: Any) -> dict:
    """类型 -> JSON Schema（递归）。"""
    origin = typing.get_origin(t)
    if origin is typing.Union:                     # Optional
        args = [a for a in typing.get_args(t) if a is not type(None)]
        s = to_schema(args[0]) if args else {"type": "string"}
        s["nullable"] = True
        return s
    if t is list or origin is list or origin is List:
        args = typing.get_args(t)
        return {"type": "array", "items": to_schema(args[0]) if args else {"type": "string"}}
    if t is dict or origin is dict or origin is Dict:
        return {"type": "object"}
    if t in _SCALAR:
        return {"type": _SCALAR[t]}
    return {"type": "string"}


def strict_schema(name: str, description: str, arg_desc: dict = None):
    """装饰器：函数签名 -> schema + 注册一个校验器。"""
    arg_desc = arg_desc or {}

    def deco(func: Callable):
        hints = typing.get_type_hints(func)
        sig = inspect.signature(func)
        properties, required = {}, []
        for pname, p in sig.parameters.items():
            anno = hints.get(pname, str)
            ps = to_schema(anno)
            if arg_desc.get(pname):
                ps["description"] = arg_desc[pname]
            if p.default is not inspect.Parameter.empty:
                if p.default is not None:
                    ps["default"] = p.default
            else:
                required.append(pname)
            properties[pname] = ps
        func._schema = {"name": name, "description": description,
                        "parameters": {"type": "object", "properties": properties,
                                       "required": required}}
        return func
    return deco


# ---------- 校验器：类型的运行时守门员 ----------

def validate(schema: dict, args: dict) -> tuple:
    """返回 (ok, 错误原因)。逐字段校对类型。"""
    props = schema["parameters"]["properties"]
    for req in schema["parameters"].get("required", []):
        if req not in args:
            return False, f"缺少必填参数 {req!r}"
    for k, v in args.items():
        p = props.get(k, {})
        t = p.get("type")
        if t == "integer" and not isinstance(v, int):
            return False, f"参数 {k!r} 应为 integer，收到 {type(v).__name__}"
        if t == "array" and not isinstance(v, list):
            return False, f"参数 {k!r} 应为 array，收到 {type(v).__name__}"
        if t == "boolean" and not isinstance(v, bool):
            return False, f"参数 {k!r} 应为 boolean"
        if t == "object" and not isinstance(v, dict):
            return False, f"参数 {k!r} 应为 object"
        if t in ("string", "number") and isinstance(v, (dict, list)):
            return False, f"参数 {k!r} 类型错误"
        if "enum" in p and v not in p["enum"]:
            return False, f"参数 {k!r} 不在枚举 {p['enum']} 内"
    return True, ""


# ---------- 工具注册（带 schema 与校验） ----------

@strict_schema("send_notification",
               "发送通知",
               arg_desc={"channel": "渠道（email / sms）", "recipient": "收件人",
                         "priority": "优先级", "tags": "标签列表"})
def send_notification(channel: str, recipient: str,
                      priority: str = "normal", tags: List[str] = None) -> dict:
    # 注意：真实实现里这里不再重复校验（守门员在上游）
    return {"ok": True, "channel": channel, "recipient": recipient,
            "priority": priority, "tags": tags or []}


# ---------- 演示：守门员拦截幻觉参数 ----------

def invoke(func: Callable, raw_args: str) -> str:
    """schema 校验 -> 执行；校验不过直接拒（模拟 deepseek tools 的严格模式）。"""
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        return "拒绝：参数不是合法 JSON"
    ok, reason = validate(func._schema, args)
    if not ok:
        return f"拒绝：{reason}（schema 守门员拦截）"
    return json.dumps(func(**args), ensure_ascii=False)


if __name__ == "__main__":
    print("演示：schema 的运行时守门员（拦截模型幻觉参数）\n")
    print("工具 schema：")
    print(" ", json.dumps(send_notification._schema, ensure_ascii=False)[:160], "…\n")

    cases = [
        '{"channel": "email", "recipient": "a@b.com"}',                  # 合法 -> 放行
        '{"channel": "email", "recipient": 12345}',                      # 类型错 -> 拒
        '{"channel": "email"}',                                          # 缺必填 -> 拒
        '{"channel": "email", "recipient": "a@b.com", "tags": "x"}',     # tags 应为数组 -> 拒
        '{"channel": "email", "recipient": "a@b.com", "tags": ["x"]}',   # 合法 -> 放行
    ]
    for c in cases:
        print(f"  输入 {c[:62]:64}-> {invoke(send_notification, c)}")

    print("""
[结论] 严格的 schema 守门员价值：
       1. 模型幻觉参数（类型错/枚举错/缺字段）在函数外被拦，函数永远收到合法输入
       2. 错误原因回传模型 → 模型自愈重试（配合 s09 的兜底精神）
       deepseek 的 ptc/py-types/ts-types 就是把这套推广到多语言、多维类型推导。""")