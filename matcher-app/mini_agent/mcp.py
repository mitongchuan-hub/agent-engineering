"""极简 MCP（Model Context Protocol）实现 —— 仅依赖标准库，无官方 SDK。

面试价值：搞懂 MCP 的本质 = JSON-RPC 2.0 + 传输层（stdio），就这么简单。

协议要点（面试三句话）：
    1. 传输：stdio 模式下，每行一个 JSON 对象（newline-delimited JSON-RPC）
    2. 生命周期：client 发 initialize 请求 -> server 回握手结果 ->
       client 发 notifications/initialized（通知，无需响应）-> 之后才能 tools/list、tools/call
    3. 错误分层：业务/工具错误放 result.isError（不是协议错误），
       协议错误（未知方法/参数错误）才放 JSON-RPC error 字段

流程示意（自己就能在黑板上画出来）：
    ┌──────────────┐  initialize          ┌──────────────┐
    │             │ ────────────────────► │             │
    │   MCP       │  ←──  protocolVersion  │   MCP        │
    │   Client    │  notifications/initialized  │   Server    │
    │   (Agent)   │ ────────────────────► │             │
    │             │  tools/list           │             │
    │             │ ────────────────────► │  compute_    │
    │             │  ←── tools 列表        │  match ...   │
    │             │  tools/call           │             │
    │             │ ────────────────────► │             │
    │             │  ←── result{content}  │             │
    └──────────────┘                      └──────────────┘
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 错误码
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603


# =============================== Server ===============================

class MCPToolServer:
    """MCP stdio 服务器：把一组 Python 函数暴露成 MCP 工具。"""

    def __init__(self, name: str = "mini-mcp-server", version: str = "0.1.0"):
        self.server_info = {"name": name, "version": version}
        self.tools: Dict[str, dict] = {}  # name -> {description, inputSchema, handler}

    def add_tool(self, name: str, description: str, input_schema: dict,
                 handler: Callable) -> None:
        """注册一个工具。input_schema 可直接复用 mini_agent 的 schema 生成器产物。"""
        self.tools[name] = {"description": description,
                            "inputSchema": input_schema, "handler": handler}

    def run_stdio(self) -> None:
        """监听 stdin，逐行应答（stdout 每行一个 JSON 响应）。"""
        # 强制 UTF-8，避免 Windows 中文环境的 GBK 管道问题
        sys.stdout.reconfigure(encoding="utf-8")
        for line in sys.stdin.buffer:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:  # 是请求 -> 需要响应；通知（无 id，如 initialized）直接忽略
                self._send(self._dispatch(msg))

    # ---------------- 内部 ----------------

    def _dispatch(self, req: dict) -> dict:
        method, params = req.get("method"), req.get("params") or {}
        try:
            if method == "initialize":
                return self._ok(req["id"], {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": self.server_info,
                })
            if method == "ping":
                return self._ok(req["id"], {})
            if method == "tools/list":
                return self._ok(req["id"], {
                    "tools": [{"name": n,
                               "description": t["description"],
                               "inputSchema": t["inputSchema"]}
                              for n, t in self.tools.items()],
                })
            if method == "tools/call":
                return self._handle_call(req["id"], params)
            return self._err(req["id"], ERR_METHOD_NOT_FOUND, f"未知方法: {method}")
        except Exception as e:  # 兜底：协议层绝对不允许把进程搞挂
            return self._err(req["id"], ERR_INTERNAL, f"内部错误: {e}")

    def _handle_call(self, rid: Any, params: dict) -> dict:
        name = params.get("name", "")
        tool = self.tools.get(name)
        if tool is None:
            return self._err(rid, ERR_INVALID_PARAMS,
                             f"未知工具: {name}，可用: {sorted(self.tools)}")
        args = params.get("arguments") or {}
        try:
            result = tool["handler"](**args)
            text = json.dumps(result, ensure_ascii=False, default=str)
            # MCP 规定：工具返回结果统一包成 content 数组；业务错误用 isError 标记
            return self._ok(rid, {"content": [{"type": "text", "text": text}],
                                  "isError": False})
        except Exception as e:
            return self._ok(rid, {"content": [{"type": "text",
                                               "text": f"工具执行失败: {type(e).__name__}: {e}"}],
                                  "isError": True})

    def _ok(self, rid: Any, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def _err(self, rid: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": code, "message": message}}

    def _send(self, obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# =============================== Client ===============================

class MCPError(Exception):
    """协议层错误（服务器返回 JSON-RPC error）。"""


class MCPClient:
    """MCP stdio 客户端：启动服务器子进程并完成握手与调用。"""

    def __init__(self, cmd: List[str], cwd: Optional[str] = None):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", cwd=cwd,
            bufsize=1,  # 行缓冲
        )
        self._next_id = 0
        self._negotiated = False

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *exc):
        self.close()

    def initialize(self) -> dict:
        result = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mini-mcp-client", "version": "0.1.0"},
        })
        self._notify("notifications/initialized")  # 握手第二步必须发
        self._negotiated = True
        return result

    def list_tools(self) -> List[dict]:
        result = self._request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> Any:
        """返回 result 中第一条 text 内容（通常可直接 json.loads）。"""
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            texts = [c.get("text", "") for c in result.get("content", [])]
            raise MCPError(texts[0] if texts else "工具执行失败")
        texts = [c.get("text", "") for c in result.get("content", [])]
        return texts[0] if texts else None

    # ---------------- 内部 ----------------

    def _request(self, method: str, params: Optional[dict] = None) -> dict:
        self._next_id += 1
        rid = self._next_id
        req = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            req["params"] = params
        self._write(req)
        while True:  # 丢弃中间的无关消息（如通知），等我们的 id 回来
            line = self.proc.stdout.readline()
            if not line:
                raise MCPError(f"服务器进程提前退出（method={method}）")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == rid:
                if "error" in msg:
                    raise MCPError(msg["error"].get("message", "协议错误"))
                return msg.get("result", {})

    def _notify(self, method: str, params: Optional[dict] = None) -> None:
        req = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            req["params"] = params
        self._write(req)

    def _write(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()