"""工具注册与 JSON Schema 自动生成。

核心思路（面试高频）：
    function calling 协议要求我们给模型一份 JSON Schema 描述每个工具。
    与其手写 schema，不如用 Python 的函数签名（inspect + type hints）自动生成
    ——「函数签名即 schema」，新增一个工具只需要写一个普通函数。

    关键特性：
    1. 类型映射：str/int/float/bool/list/dict/Optional -> JSON Schema
    2. 有默认值的参数自动标记为"非必填"
    3. 工具执行异常不会被吞掉，而是以错误字符串返回给模型，让模型自愈重试
"""
from __future__ import annotations

import inspect
import json
import traceback
import typing
from typing import Any, Callable, Dict, List, Optional

_SCALAR = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _to_schema_type(t: Any) -> Dict[str, Any]:
    """把 Python 类型转成 JSON Schema 类型（递归）。"""
    origin = typing.get_origin(t)

    # Optional[str] / Union[str, None] -> 可空字段
    if origin is typing.Union:
        args = [a for a in typing.get_args(t) if a is not type(None)]
        schema = _to_schema_type(args[0]) if args else {"type": "string"}
        schema["nullable"] = True
        return schema

    # list[str] / List[str]
    if origin is list or origin is List:
        args = typing.get_args(t)
        items = _to_schema_type(args[0]) if args and args[0] is not Any else {"type": "string"}
        return {"type": "array", "items": items}

    # dict / Dict[str, str]
    if origin is dict or origin is Dict:
        return {"type": "object"}

    # 标量
    if t in _SCALAR:
        return {"type": _SCALAR[t]}

    # 兜底：未知类型一律按字符串（宁可宽松，不可让模型报错）
    return {"type": "string"}


class Tool:
    """一个可被 Agent 调用的工具。"""

    def __init__(self, func: Callable, name: Optional[str] = None,
                 description: Optional[str] = None, arg_desc: Optional[dict] = None):
        self.func = func
        self.name = name or func.__name__
        doc = inspect.getdoc(func) or ""
        self.description = (description or doc).strip() or func.__name__
        self.arg_desc = arg_desc or {}
        self.schema = self._build_schema()

    def _build_schema(self) -> dict:
        """由函数签名自动生成 {name, description, parameters} 三段式 schema。"""
        try:
            hints = typing.get_type_hints(self.func)
        except Exception:
            hints = {}
        sig = inspect.signature(self.func)
        properties, required = {}, []
        for pname, p in sig.parameters.items():
            if pname in ("self", "cls") or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            # get_type_hints 会把字符串注解（from __future__ import annotations）
            # 解析成真实类型；解析失败时退回原始注解。
            anno = hints.get(pname, p.annotation)
            if anno in (inspect.Parameter.empty, None):
                anno = str
            try:
                pschema = _to_schema_type(anno)
            except Exception:
                pschema = {"type": "string"}
            if self.arg_desc.get(pname):
                pschema["description"] = self.arg_desc[pname]
            # 有默认值 -> 非必填，并给出 default 提示模型
            if p.default is not inspect.Parameter.empty:
                if p.default is not None and not isinstance(p.default, (dict, list)):
                    pschema["default"] = p.default
            else:
                required.append(pname)
            properties[pname] = pschema
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        }

    def __call__(self, **kwargs):
        return self.func(**kwargs)


class ToolRegistry:
    """工具注册表：注册、导出 schema（给模型看）、执行（给模型用）。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, t: Tool) -> Tool:
        self._tools[t.name] = t
        return t

    def tool(self, name: Optional[str] = None, description: Optional[str] = None,
             arg_desc: Optional[dict] = None):
        """装饰器用法：@registry.tool(description="...") def my_tool(...): ..."""
        def deco(func: Callable) -> Tool:
            return self.register(Tool(func, name=name, description=description, arg_desc=arg_desc))
        return deco

    def schemas(self) -> List[dict]:
        """导出 OpenAI tools 协议格式的 schema 列表。"""
        return [{"type": "function", "function": t.schema} for t in self._tools.values()]

    def call(self, name: str, arguments: Any) -> str:
        """执行工具并返回**字符串**结果（tool message 要求字符串）。"""
        t = self._tools.get(name)
        if t is None:
            return f"错误：未知工具 '{name}'。可用工具：{sorted(self._tools)}"
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
            if not isinstance(args, dict):
                return f"错误：工具参数必须是 JSON 对象，收到：{arguments!r}"
            result = t.func(**args)
            return json.dumps(result, ensure_ascii=False, default=str)
        except TypeError as e:
            # 参数不对：告诉模型怎么改，让它重试
            return f"工具调用参数错误：{e}。请参考工具 schema 修正参数后重试。"
        except Exception as e:
            # 业务异常：同样回传，模型可以自主决定重试或换方案（agent 健壮性）
            return f"工具执行失败：{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"