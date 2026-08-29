"""MCP 协议端到端测试：真实拉起 app/mcp_server.py 子进程，
走完整握手（initialize -> notifications/initialized -> tools/list -> tools/call），
验证协议层 + schema 复用 + 错误分层。无需网络/key。

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from mini_agent.mcp import MCPClient, MCPError  # noqa: E402


def _spawn():
    server_script = str(PROJECT_ROOT / "app" / "mcp_server.py")
    return MCPClient([sys.executable, "-u", server_script], cwd=str(PROJECT_ROOT))


class TestMCPProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = _spawn()  # 显式完成握手（initialize + notifications/initialized）
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_handshake_result(self):
        self.assertTrue(self.client._negotiated)

    def test_list_tools(self):
        tools = self.client.list_tools()
        names = {t["name"] for t in tools}
        self.assertIn("compute_match", names)
        self.assertIn("read_text_file", names)
        # 每个工具都带 MCP 要求的 inputSchema
        cm = next(t for t in tools if t["name"] == "compute_match")
        self.assertEqual(cm["inputSchema"]["type"], "object")
        self.assertIn("resume_text", cm["inputSchema"]["properties"])

    def test_call_tool(self):
        out = self.client.call_tool("compute_match", {
            "resume_text": "3 年硕士 Python LLM RAG Agent",
            "jd_text": "2 年以上 硕士 Python LLM RAG Agent",
        })
        r = json.loads(out)
        self.assertIn("overall_score", r)
        self.assertGreaterEqual(r["overall_score"], 80)  # 全命中 -> 高分

    def test_arguments_as_json_string(self):
        """回归：部分模型把 arguments 序列化成 JSON 字符串，桥接层必须容错。"""
        from app.mcp_tools import _coerce_args
        self.assertEqual(_coerce_args("{\"a\": 1}"), {"a": 1})
        self.assertEqual(_coerce_args({"a": 1}), {"a": 1})
        self.assertEqual(_coerce_args(None), {})

    def test_business_error_vs_protocol_error(self):
        """业务错误（工具抛异常）→ result.isError；未知工具 → JSON-RPC error。"""
        # 业务错误：read 不存在路径
        err = self.client.call_tool("read_text_file", {"path": "/no/such/file.md"})
        r = json.loads(err)
        self.assertIn("error", r)  # 工具返回的是 error 字典，不是 JSON-RPC error

        # 协议错误：未知工具
        with self.assertRaises(MCPError) as ctx:
            self.client.call_tool("not_exist_tool", {})
        self.assertIn("未知工具", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)