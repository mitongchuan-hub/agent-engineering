"""mini_agent 单元测试（stdlib unittest，无需网络/API key）。

验证点（对应面试题）：
    1. 函数签名 ➜ JSON Schema 生成的正确性（类型/必填/默认值）
    2. registry.call 的三类异常兜底（未知工具/坏参数/执行抛错）
    3. Agent 主循环：假 LLM 模拟多轮工具调用 ➜ 工具结果正确回填 ➜ 最终回答
    4. MessageBuffer 超预算截断：system 保留、不拆散 tool 问答对

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from typing import List, Optional

from mini_agent.agent import Agent
from mini_agent.memory import MessageBuffer
from mini_agent.tools import Tool, ToolRegistry


# ---------------- 测试用工具 ----------------

class _FakeLLM:
    """脚本化假 LLM：按预设剧本依次返回「工具调用/最终回答」。"""
    def __init__(self, script):
        self.script = list(script)
        self.calls = []          # 记录每次收到的 messages（供断言）
        self.received_tools = [] # 记录每次收到的 tools schema

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        self.received_tools.append(tools)
        return self.script.pop(0)


class TestSchemaGeneration(unittest.TestCase):
    def test_types_and_required(self):
        def tool_fn(name: str, years: int, tags: List[str], ratio: float = 0.5,
                    note: Optional[str] = None, enabled: bool = True) -> str:
            """给候选人打分"""
            return name

        t = Tool(tool_fn)
        p = t.schema["parameters"]
        self.assertEqual(t.schema["name"], "tool_fn")
        self.assertIn("打分", t.description)
        self.assertEqual(p["properties"]["name"]["type"], "string")
        self.assertEqual(p["properties"]["years"]["type"], "integer")
        self.assertEqual(p["properties"]["tags"]["type"], "array")
        self.assertEqual(p["properties"]["ratio"]["type"], "number")
        self.assertEqual(p["properties"]["enabled"]["type"], "boolean")
        self.assertTrue(p["properties"]["note"].get("nullable"))
        # 必填 = 无默认值参数
        self.assertEqual(set(p["required"]), {"name", "years", "tags"})


class TestRegistryCall(unittest.TestCase):
    def setUp(self):
        self.r = ToolRegistry()

        @self.r.tool(description="加总")
        def add(a: int, b: int) -> int:
            return a + b

        @self.r.tool(description="必然失败")
        def boom(x: int) -> int:
            raise ValueError("内部错误")

    def test_ok(self):
        self.assertEqual(self.r.call("add", '{"a": 1, "b": 2}'), "3")

    def test_unknown_tool(self):
        out = self.r.call("nope", "{}")
        self.assertIn("未知工具", out)
        self.assertIn("add", out)

    def test_bad_args(self):
        out = self.r.call("add", '{"a": "x"}')
        self.assertIn("参数错误", out)

    def test_exception_boundary(self):
        """工具抛异常不能炸掉 Agent，需返回错误串让模型自愈。"""
        out = self.r.call("boom", '{"x": 1}')
        self.assertIn("执行失败", out)
        self.assertIn("ValueError", out)


class TestAgentLoop(unittest.TestCase):
    def _agent(self, script):
        registry = ToolRegistry()

        @registry.tool(description="乘法")
        def mul(a: int, b: int) -> int:
            return a * b

        fake = _FakeLLM(script)
        ag = Agent(llm=fake, registry=registry, system_prompt="你是计算器",
                   max_iters=5)
        return ag, fake

    def test_multi_tool_then_answer(self):
        """两轮工具调用后给出最终回答。"""
        script = [
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "mul", "arguments": '{"a": 6, "b": 7}'}}]},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c2", "type": "function",
                             "function": {"name": "mul", "arguments": '{"a": -1, "b": 3}'}}]},
            {"role": "assistant", "content": "答案是 42 和 -3", "tool_calls": None},
        ]
        ag, fake = self._agent(script)
        out = ag.run("6*7 和 -1*3 等于几", verbose=False)
        self.assertEqual(out, "答案是 42 和 -3")
        # 工具结果必须回填给模型（tool 消息带着 tool_call_id）
        tool_msgs = [m for m in ag.buffer.messages if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 2)
        self.assertEqual(tool_msgs[0]["tool_call_id"], "c1")
        self.assertEqual(tool_msgs[0]["content"], "42")
        self.assertEqual(tool_msgs[1]["tool_call_id"], "c2")
        self.assertEqual(tool_msgs[1]["content"], "-3")
        # 每轮调用都必须把 tools schema 传给模型
        self.assertTrue(all(t is not None for t in fake.received_tools))

    def test_immediate_answer(self):
        """模型第一轮就回答，不调工具。"""
        script = [{"role": "assistant", "content": "直接答", "tool_calls": None}]
        ag, _ = self._agent(script)
        self.assertEqual(ag.run("hi", verbose=False), "直接答")


class TestMessageBuffer(unittest.TestCase):
    def test_trim_keeps_system_and_pairs(self):
        buf = MessageBuffer(system_prompt="SYS", char_budget=300)
        for i in range(10):
            buf.add({"role": "assistant", "content": "q", "tool_calls": [{"id": f"c{i}"}]})
            buf.add({"role": "tool", "tool_call_id": f"c{i}", "content": "r" * 60})
        sent = buf.for_llm
        self.assertEqual(sent[0]["role"], "system")
        # 不能出现孤立的 tool 消息（它前面必须紧跟同组的 assistant）
        for m in sent:
            if m.get("role") == "tool":
                idx = sent.index(m)
                self.assertEqual(sent[idx - 1]["role"], "assistant")
                self.assertEqual(sent[idx - 1]["tool_calls"][0]["id"], m["tool_call_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)