"""上下文管理：MessageBuffer（字符预算 + 窗口截断）。

面试题：「Agent 的 context 会无限膨胀，怎么解决？」
标准答案三条路：
    1. 窗口截断（这里实现）——超出预算时从最早的消息开始丢
    2. 摘要压缩     ——把旧对话压成一段 summary 放进 system
    3. 向量检索     ——RAG，只把相关片段塞进上下文
生产级系统通常是 1+2+3 组合。mini_agent 先实现最基础的 1，
并且保证截断时**不会拆散一次工具调用的问答对**（assistant 发起 -> tool 回填），
否则模型会看到"孤儿"的 tool 消息而困惑。
"""
from __future__ import annotations

import json
from typing import List


def _size(msg: dict) -> int:
    """粗估一条消息的 token 量：JSON 字符数（中文 1 字符≈1 token 量级，够用）。"""
    return len(json.dumps(msg, ensure_ascii=False))


class MessageBuffer:
    def __init__(self, system_prompt: str, char_budget: int):
        self.system = {"role": "system", "content": system_prompt}
        self.char_budget = char_budget
        self.messages: List[dict] = []

    def add(self, msg: dict):
        self.messages.append(msg)

    def reset(self):
        """开新一轮对话：只保留 system（Agent.run 每次任务开始时调用）。"""
        self.messages = []

    def _turns(self) -> List[List[dict]]:
        """把消息流切成一个个「回合」：assistant 消息 + 其后的 tool/user 消息，直到下一条 assistant。"""
        turns, cur = [], []
        for m in self.messages:
            if m.get("role") == "assistant" and cur:
                turns.append(cur)
                cur = []
            cur.append(m)
        if cur:
            turns.append(cur)
        return turns

    @property
    def for_llm(self) -> List[dict]:
        """从尾部向前保留尽量多的回合，直到字符预算上限。"""
        base = _size(self.system)
        kept, used = [], base
        for turn in reversed(self._turns()):
            cost = sum(_size(m) for m in turn)
            # 预算不够了就不再加；但如果一个回合都放不下，至少放最新那条
            if used + cost > self.char_budget and kept:
                break
            kept = turn + kept
            used += cost
        return [self.system] + kept

    def stats(self) -> dict:
        return {"total_msgs": len(self.messages),
                "sent_msgs": len(self.for_llm),
                "budget_chars": self.char_budget,
                "used_chars": sum(_size(m) for m in self.for_llm)}