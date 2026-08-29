"""端到端协议联调测试：本地起一个假的 OpenAI 兼容服务器，验证
ChatClient(openai SDK) + registry + Agent 全链路（不需要真 API key）。

假服务器按请求次数回放脚本：第 1 次让模型调 list_files，第 2 次调 compute_match，
第 3 次给最终回答。真实工具会真正执行并回填。

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from mini_agent.agent import Agent
from mini_agent.llm import ChatClient
from mini_agent.tools import ToolRegistry


class FakeOpenAIServer:
    """极简 OpenAI /v1/chat/completions 假实现。"""

    def __init__(self):
        self.request_count = 0
        self.last_messages = None  # 记录收到的 messages 供断言

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # 静默
                pass

            def do_POST(self):
                state = self.server.fake  # 指向 FakeOpenAIServer 实例
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state.last_messages = body.get("messages", [])
                state.request_count += 1
                n = state.request_count

                if n == 1:
                    message = {
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": "call_1", "type": "function",
                            "function": {"name": "list_files",
                                         "arguments": '{"directory": "app/data"}'},
                        }],
                    }
                    finish = "tool_calls"
                elif n == 2:
                    message = {
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": "call_2", "type": "function",
                            "function": {"name": "compute_match",
                                         "arguments": json.dumps({
                                             "resume_text": "3 年经验 Python LLM RAG Agent 硕士",
                                             "jd_text": "要求 Python LLM 硕士 2 年以上",
                                         }, ensure_ascii=False)},
                        }],
                    }
                    finish = "tool_calls"
                else:
                    message = {"role": "assistant",
                               "content": "联调成功：文件与匹配工具都工作正常",
                               "tool_calls": None}
                    finish = "stop"

                payload = {
                    "id": f"chatcmpl-{n}", "object": "chat.completion", "created": 0,
                    "model": "fake-model",
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        httpd.fake = self  # 让 handler 能访问状态
        self.port = httpd.server_address[1]
        self.httpd = httpd
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestProtocolE2E(unittest.TestCase):
    def test_full_chain(self):
        srv = FakeOpenAIServer()
        try:
            # 真实 ChatClient，指向假服务器
            llm = ChatClient(base_url=f"http://127.0.0.1:{srv.port}/v1",
                             api_key="fake-key", model="fake-model")
            registry = ToolRegistry()

            from app.tools import register_domain_tools
            register_domain_tools(registry)

            agent = Agent(llm=llm, registry=registry, system_prompt="联调", max_iters=5)
            out = agent.run("请扫描目录里的文件并评估匹配", verbose=False)

            self.assertIn("联调成功", out)
            # 3 次请求：工具调用 x2 + 最终回答
            self.assertEqual(srv.request_count, 3)
            # 工具结果（AA 的结构化 JSON）必须通过协议回传给了模型
            all_text = json.dumps(srv.last_messages, ensure_ascii=False)
            self.assertIn("overall_score", all_text)
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)