"""Agent 主循环（ReAct / tool-calling）——整个框架的心脏。

伪代码（面试请背这一段）：
    repeat (最多 max_iters 次):
        1. resp = LLM(messages, tools)          # 模型思考：要么给最终回答，要么请求调用工具
        2. messages.append(resp)
        3. if resp 没有 tool_calls:             # 任务完成
               return resp 的内容
        4. for tc in resp.tool_calls:           # 模型要调多个工具
               result = registry.call(name, args)
               messages.append({"role":"tool", content: result})
    # 超了迭代上限：再让模型收个尾，别让它无限循环

健壮性要点（面试追问）：
    - 工具参数错误/执行失败 -> 以字符串回传模型，让它自愈（不直接崩溃）
    - 迭代上限 -> 防止死循环烧钱
    - 上下文预算 -> MessageBuffer 兜底
"""
from __future__ import annotations

import json
from typing import Optional

from mini_agent.llm import ChatClient, LLMError, pretty_args
from mini_agent.memory import MessageBuffer
from mini_agent.tools import ToolRegistry


class Agent:
    def __init__(self, llm: ChatClient, registry: ToolRegistry,
                 system_prompt: str, max_iters: int = 12, char_budget: int = 24000):
        self.llm = llm
        self.registry = registry
        self.buffer = MessageBuffer(system_prompt, char_budget)
        self.max_iters = max_iters

    @property
    def tools_description(self) -> str:
        return ", ".join(sorted(self.registry._tools))

    def run(self, user_input: str, verbose: bool = True) -> str:
        """执行一次任务，返回最终文本回答。"""
        self.buffer.reset()
        self.buffer.add({"role": "user", "content": user_input})
        if verbose:
            print(f"[agent] 开始任务：{user_input[:60]}{'...' if len(user_input) > 60 else ''}")
            print(f"[agent] 可用工具：{self.tools_description}")

        for step in range(1, self.max_iters + 1):
            # 第 1 步：模型思考 -> 回答或请求工具
            resp = self.llm.chat(self.buffer.for_llm, tools=self.registry.schemas())
            self.buffer.add(resp)

            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                if verbose:
                    print(f"[agent] step {step}: 模型给出最终回答（无工具调用），结束")
                    print(f"[agent] 上下文统计：{self.buffer.stats()}")
                return resp.get("content") or "(模型返回了空回答)"

            # 第 2 步：执行所有被请求的工具调用（可并行，这里顺序执行）
            if verbose:
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    args = pretty_args(tc["function"]["arguments"])
                    print(f"[agent] step {step}: 调用工具 {name}({args})")
            for tc in tool_calls:
                name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]
                result = self.registry.call(name, raw_args)
                self.buffer.add({"role": "tool", "tool_call_id": tc["id"],
                                 "content": result[:2000]})  # 截断超长结果，防爆上下文
                if verbose:
                    print(f"[agent] step {step}: {name} 返回 {result[:200]}...")

        # 第 3 步：超迭代上限。不再给工具，强制模型基于已有信息收尾。
        if verbose:
            print(f"[agent] 达到 {self.max_iters} 步上限，要求模型收尾")
        wrapup = self.llm.chat(self.buffer.for_llm(), tools=None)
        return wrapup.get("content") or "(模型未产出回答)"