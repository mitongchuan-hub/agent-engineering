#!/usr/bin/env python3
"""
s03_llm_client.py - LLM 客户端：模型无关，协议统一

s01/s02 调用模型还是"演示模型"。这一章解决"真实模型怎么接"：

    核心思想：所有主流大模型服务（OpenAI/DeepSeek/智谱/Moonshot/通义……）
    都实现了 OpenAI 兼容协议。把「协议差异」封在一个 ChatClient 类里，
    业务代码从此只面向一个稳定的接口：

        ChatClient(base_url, api_key, model).chat(messages, tools) -> assistant 消息

    换模型 = 改 base_url + model 两个字符串，代码零改动。

本文件在无 Key 时启动一个「本地假 OpenAI 服务器」，让真实 ChatClient
走一遍完整 HTTP 协议（亲眼看到请求/响应格式），再对比真模型用法。

Usage:
    python s03_llm_client/code.py           # 演示：本地假服务器验证协议
    LLM_API_KEY=sk-xxx python s03_llm_client/code.py   # 真实模型
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- ① 配置

def load_env() -> None:
    """读取 .env：向上回溯找到的第一份（密钥统一放仓库根 .env）。"""
    if os.getenv("LEARN_NO_ENV"):  # 一键回归 scripts/check_all.py 强制演示模式
        return
    here = Path(__file__).resolve()
    for base in [here.parent, here.parent.parent, here.parent.parent.parent]:
        p = base / ".env"
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k:
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return


load_env()

API_KEY = os.getenv("LLM_API_KEY", "")
IS_REAL = bool(API_KEY) and not API_KEY.startswith("sk-your")


# ---------------------------------------------------------------- ② ChatClient（核心类）

class LLMError(Exception):
    """LLM 调用层错误：统一抛给上层处理（如自动重试）。"""


class ChatClient:
    """OpenAI 兼容客户端。

    面试点：为什么把协议差异封一层？
      - 业务代码只依赖 ChatClient 的接口，不依赖具体厂商
      - 换模型/加厂商 = 改两个配置字符串
      - 错误类型统一（LLMError），上层可按需重试
    """

    def __init__(self, base_url: str = "", api_key: str = "",
                 model: str = "", temperature: float = 0.3, timeout: int = 120):
        # 行业惯例：OpenAI 兼容服务都挂在 /v1 下，用户可能只给域名，自动补齐
        base_url = (base_url or "https://api.deepseek.com/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        self.base_url, self.api_key, self.model = base_url, api_key, model or "deepseek-chat"
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None,
             transport=None) -> Dict[str, Any]:
        """一次对话请求（transport 可注入，便于测试/演示）。

        Returns 标准 assistant 消息：
            {"role": "assistant", "content": str,
             "tool_calls": [{"id", "function": {"name", "arguments"}}] | None}
        """
        if transport is not None:
            # 演示模式：用注入的 transport 发送 HTTP（下面 FakeServer 演示）
            return transport.chat(self.base_url, self.api_key, self.model,
                                  messages, tools, self.temperature)

        # 真实模式：走 openai SDK
        try:
            from openai import OpenAI
            client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)
        except ImportError:
            raise LLMError(
                "真实模式需要 openai 依赖（请先 pip install -r requirements.txt）。"
                "若只想看演示：移开仓库根 .env 或让其不含 LLM_API_KEY。") from None
        except Exception as e:
            raise LLMError(f"openai SDK 初始化失败: {e}") from e
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages,
                                  "temperature": self.temperature}
        if tools:
            kwargs["tools"] = tools
        try:
            msg = client.chat.completions.create(**kwargs).choices[0].message
        except Exception as e:
            raise LLMError(f"LLM 请求失败（{self.model}）: {e}")
        return {
            "role": "assistant", "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "function": {"name": tc.function.name,
                                           "arguments": tc.function.arguments}}
                for tc in (msg.tool_calls or [])
            ] or None,
        }


# ---------------------------------------------------------------- ③ 演示：本地假 OpenAI 服务器

class FakeOpenAITransport:
    """极简 /v1/chat/completions 假实现 + 同步 transport。

    它记录收到的请求体（便于验证协议），并按脚本返回 tool_calls/回答。
    这样即使没有 Key，也能看到「请求里带了什么、响应里返回什么」。
    """

    def __init__(self):
        self.received: List[dict] = []
        self.count = 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                state = self.server.fake  # BaseHTTPRequestHandler.server 指向 httpd
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                state.received.append(body)
                state.count += 1
                n = state.count
                if n == 1:
                    message = {"role": "assistant", "content": None, "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'}}]}
                    finish = "tool_calls"
                else:
                    message = {"role": "assistant", "content": "1 + 2 = 3", "tool_calls": None}
                    finish = "stop"
                resp = {"id": f"chatcmpl-{n}", "object": "chat.completion", "created": 0,
                        "model": body.get("model"), "choices": [
                            {"index": 0, "message": message, "finish_reason": finish}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        httpd.fake = self
        self.httpd = httpd
        self.port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def chat(self, base_url, api_key, model, messages, tools, temperature):
        """驱动真实 HTTP 请求打本地假服务器。"""
        import urllib.request
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            data=json.dumps({"model": model, "messages": messages,
                             "tools": tools or [], "temperature": temperature}).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key or 'demo'}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        return {"role": "assistant", "content": msg.get("content"),
                "tool_calls": msg.get("tool_calls") or None}


# ---------------------------------------------------------------- ④ 演示

if __name__ == "__main__":
    CHAT = ChatClient(base_url=os.getenv("LLM_BASE_URL", ""),
                      api_key=API_KEY, model=os.getenv("LLM_MODEL", ""))

    if IS_REAL:
        print(f"真实模式：{CHAT.base_url} / {CHAT.model}")
        resp = CHAT.chat([{"role": "user", "content": "1+2 等于几？用工具算"}],
                         tools=[{"type": "function", "function": {
                             "name": "add", "description": "加法",
                             "parameters": {"type": "object", "properties": {
                                 "a": {"type": "integer"}, "b": {"type": "integer"}},
                                 "required": ["a", "b"]}}}])
        print("响应：", json.dumps(resp, ensure_ascii=False, indent=1)[:400])
    else:
        print("演示模式：本地假 OpenAI 服务器（无需 Key，验证协议流程）")
        fake = FakeOpenAITransport()
        resp1 = CHAT.chat([{"role": "user", "content": "计算 1+2"}],
                          tools=[], transport=fake)
        print("第一次调用返回：", json.dumps(resp1, ensure_ascii=False)[:200])

        # 看看我们的请求到底发出了什么（协议长什么样）
        req = fake.received[0] if fake.received else {}
        print("\n[协议观察] 发给服务器的请求体：")
        print("  model     :", req.get("model"))
        print("  messages  :", json.dumps(req.get("messages"), ensure_ascii=False)[:120])
        print("  tools     :", json.dumps(req.get("tools"), ensure_ascii=False)[:120])

        memo = [{"role": "user", "content": "计算 1+2"},
                {"role": "assistant", "content": None,
                 "tool_calls": [{"id": "c1", "type": "function",
                                 "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "3"}]
        resp2 = CHAT.chat(memo, tools=[], transport=fake)
        print("\n第二次调用（带工具结果回填）返回：", json.dumps(resp2, ensure_ascii=False)[:150])
        print("\n[结论] ChatClient 隔离了协议细节：任何模型换 base_url+model 即可接入。")
        fake.httpd.shutdown()
    print("done")