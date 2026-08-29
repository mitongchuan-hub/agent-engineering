#!/usr/bin/env python3
"""
s07_mcp_server.py - MCP 协议：从零实现一个 Server

MCP（Model Context Protocol）是 2025 年最热的 Agent 协议，
面试几乎必问"什么是 MCP"。这一章不依赖官方 SDK，
用纯标准库实现协议核心，一次看懂它的本质：

    MCP = JSON-RPC 2.0 + 传输层（stdio = 每行一个 JSON）

生命周期（面试手绘版）：
    Client ── initialize ──────────────▶ Server
    Client ◀─ protocolVersion/capabilities ── Server
    Client ── notifications/initialized ──▶ Server   (通知,无响应)
    Client ── tools/list ──────────────▶ Server
    Client ◀─ 工具列表 ────────────────── Server
    Client ── tools/call compute_match ─▶ Server     (步骤 s05 的打分器!)
    Client ◀─ result{content} ────────── Server

错误分层（面试细节）：
    业务/工具错误  -> result.isError = true（工具返回的"业务失败"）
    协议错误        -> JSON-RPC error 字段（未知方法/参数错误）

Usage:
    python s07_mcp_server/code.py            # 演示：子进程跑 server + client 走完整协议
    python s07_mcp_server/code.py --serve    # 作为 MCP Server 常驻（供任意客户端连）
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------- ① 一个待暴露的工具（复用 s05）

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from s05_matcher.code import compute_match  # noqa: E402

# MCP 工具描述：name/description/inputSchema（JSON Schema）
MCP_TOOLS = {
    "compute_match": {
        "description": "简历×JD 匹配打分，返回 JSON（技能/年限/学历/总分/结论）",
        "inputSchema": {"type": "object", "properties": {
            "resume_text": {"type": "string", "description": "简历全文"},
            "jd_text": {"type": "string", "description": "岗位 JD 全文"}},
            "required": ["resume_text", "jd_text"]},
        "handler": compute_match,
    },
}


# ---------------------------------------------------------------- ② Server：JSON-RPC 分发

class MCPToolServer:
    """stdio MCP 服务器：stdin 读请求，stdout 写响应，每行一个 JSON。"""

    PROTOCOL_VERSION = "2024-11-05"

    def run_stdio(self) -> None:
        sys.stdout.reconfigure(encoding="utf-8")
        for line in sys.stdin.buffer:                      # 逐行读
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:                                # 请求 -> 响应
                self._send(self._dispatch(msg))
            # 通知（无 id，如 notifications/initialized）-> 忽略

    def _dispatch(self, req: dict) -> dict:
        rid, method, params = req.get("id"), req.get("method"), req.get("params") or {}
        if method == "initialize":
            return self._ok(rid, {"protocolVersion": self.PROTOCOL_VERSION,
                                  "capabilities": {"tools": {"listChanged": False}},
                                  "serverInfo": {"name": "mini-mcp-server", "version": "0.1.0"}})
        if method == "ping":
            return self._ok(rid, {})
        if method == "tools/list":
            return self._ok(rid, {"tools": [
                {"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                for n, t in MCP_TOOLS.items()]})
        if method == "tools/call":
            return self._call(rid, params)
        return self._err(rid, -32601, f"未知方法: {method}")

    def _call(self, rid, params: dict) -> dict:
        name, tool = params.get("name", ""), MCP_TOOLS.get(params.get("name", ""))
        if tool is None:
            return self._err(rid, -32602, f"未知工具: {name}，可用: {sorted(MCP_TOOLS)}")
        try:
            text = json.dumps(tool["handler"](**params.get("arguments") or {}),
                              ensure_ascii=False, default=str)
            return self._ok(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:                               # 业务错误：isError，不是协议错误
            return self._ok(rid, {"content": [{"type": "text",
                                               "text": f"工具执行失败: {type(e).__name__}: {e}"}],
                                  "isError": True})

    def _ok(self, rid, result) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def _err(self, rid, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    def _send(self, obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------- ③ Client：握手 + 调用

class MCPClient:
    """stdio MCP 客户端：拉起 server 子进程并走完整生命周期。"""

    def __init__(self, cmd: List[str]):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, encoding="utf-8", bufsize=1)
        self._id = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        return False

    def request(self, method: str, params: dict = None) -> dict:
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            req["params"] = params
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server 提前退出")
            msg = json.loads(line)
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "协议错误"))
                return msg.get("result", {})

    def put_notification(self, method: str) -> None:      # 通知：无 id、无需响应
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()


# ---------------------------------------------------------------- ④ 演示

SAMPLE_RESUME = "3 年经验，硕士，Python LLM RAG Agent LangChain"
SAMPLE_JD = "要求 2 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch"


def demo() -> None:
    print("MCP 协议演示（子进程拉起真实 Server，无需 Key）\n")
    client = MCPClient([sys.executable, "-u", str(Path(__file__).resolve()), "--serve"])

    # ① 握手
    r = client.request("initialize", {"protocolVersion": "2024-11-05",
                                      "capabilities": {},
                                      "clientInfo": {"name": "demo", "version": "0.0.1"}})
    print(f"① initialize -> protocolVersion={r['protocolVersion']}, server={r['serverInfo']['name']}")
    client.put_notification("notifications/initialized")   # ② 握手第二步

    # ③ 列工具
    tools = client.request("tools/list").get("tools", [])
    print(f"② tools/list -> 发现 {len(tools)} 个工具: {[t['name'] for t in tools]}")
    print(f"   其中一个的 inputSchema: {json.dumps(tools[0]['inputSchema'], ensure_ascii=False)[:90]}...")

    # ④ 调工具（把 s05 的打分器搬进协议）
    result = client.request("tools/call", {"name": "compute_match",
                                           "arguments": {"resume_text": SAMPLE_RESUME,
                                                         "jd_text": SAMPLE_JD}})
    text = result["content"][0]["text"]
    score = json.loads(text)["overall_score"]
    print(f"③ tools/call compute_match -> 总分 {score}（isError={result['isError']}）")

    # ⑤ 协议错误 vs 业务错误（面试细节）
    try:
        client.request("tools/call", {"name": "not_exist"})
    except RuntimeError as e:
        print(f"④ 未知工具 -> JSON-RPC error: {e}")
    bad = client.request("tools/call", {"name": "compute_match",
                                        "arguments": {"resume_text": ""}})  # 缺 jd_text
    print(f"⑤ 参数不全 -> result.isError={bad['isError']}（业务错误 vs 协议错误分层）")

    client.proc.terminate()
    print("\n[结论] MCP 没有魔法：JSON-RPC 请求/响应 + stdio 行传输，仅此而已。")


if __name__ == "__main__":
    if "--serve" in sys.argv:
        # 常驻模式：给任意 MCP 客户端做服务
        MCPToolServer().run_stdio()
    else:
        demo()