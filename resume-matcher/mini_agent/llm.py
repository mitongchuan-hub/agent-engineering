"""统一 LLM 客户端（OpenAI 兼容协议）。

只要服务商支持 OpenAI 协议（OpenAI / DeepSeek / 智谱 / Moonshot / Qwen），
改 base_url + model 就能切换，业务代码零改动。这也是面试里的架构题：
「你的 Agent 怎么做到模型无关？」——把协议差异封在 client 一层。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

# 统一的消息格式（dict），方便 MessageBuffer 存管与序列化：
#   {"role": "user"|"assistant"|"tool"|"system", "content": str, ...}


class LLMError(Exception):
    """LLM 调用层错误，统一抛给上层处理。"""


class ChatClient:
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.3, timeout: int = 120,
                 extra_body: Optional[dict] = None):
        # 行业惯例：OpenAI 兼容服务一律挂在 /v1 下；用户可能只给域名，这里自动补齐
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model = model
        self.temperature = temperature
        self.extra_body = extra_body or {}

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> Dict[str, Any]:
        """一次对话请求。

        Returns:
            标准 assistant 消息 dict：
                {"role": "assistant", "content": str,
                 "tool_calls": [{"id", "function": {"name", "arguments"}}] | None}
        """
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages,
                                  "temperature": self.temperature}
        if tools:
            kwargs["tools"] = tools
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMError(f"LLM 请求失败（{self.model}）: {e}") from e

        if not resp.choices:
            raise LLMError("LLM 返回了空 choices")
        msg = resp.choices[0].message

        tool_calls = None
        if getattr(msg, "tool_calls", None):
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        return {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": tool_calls,  # 没有工具调用时为 None
        }

    def __repr__(self):  # 便于 debug
        return f"ChatClient(model={self.model}, base_url={self.client.base_url})"


def pretty_args(raw: str) -> str:
    """把工具调用参数 JSON 打印成可读文本（用于 verbose 日志）。"""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except Exception:
        return raw