#!/usr/bin/env python3
"""
s04_context_memory.py - 上下文管理：预算 + 窗口截断

Agent 跑久了，messages 会越来越长，最终爆掉模型的 context window。
这一章解决"上下文无限膨胀"：

    三大解法（面试标准答案）：
    1. 窗口截断（本章实现）：超预算就从最早的消息开始丢
    2. 摘要压缩：把旧对话压成一段 summary 塞进 system（生产常用，稍复杂）
    3. 向量检索：RAG，只把相关片段塞进上下文（又一层复杂度）

    生产级 Agent 通常 1+2+3 组合。这里实现最基础的 1，
    并且保证截断时绝不拆散"一次工具调用的问答对"
    （assistant 发起 tool_call -> tool 回填结果，必须成对保留），
    否则模型会看到"孤儿"的 tool 消息而困惑。

Usage:
    python s04_context_memory/code.py        # 演示：观察截断行为
"""

import json
import os
import sys
from pathlib import Path
from typing import List


def load_env() -> None:
    """读取 .env：向上回溯找到的第一份（密钥统一放仓库根 .env）。"""
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
                    os.environ.setdefault(k.strip(), v.strip())
        return


load_env()


# ---------------------------------------------------------------- 核心：MessageBuffer

def _size(msg: dict) -> int:
    """粗估一条消息的 token 量：JSON 字符数（够演示用，中文 1 字符≈1 token 量级）。"""
    return len(json.dumps(msg, ensure_ascii=False))


class MessageBuffer:
    """带字符预算的上下文容器。"""

    def __init__(self, system_prompt: str, char_budget: int):
        self.system = {"role": "system", "content": system_prompt}
        self.char_budget = char_budget
        self.messages: List[dict] = []

    def add(self, msg: dict) -> None:
        self.messages.append(msg)

    def reset(self) -> None:
        """开新一轮任务：只保留 system。"""
        self.messages = []

    def _turns(self) -> List[List[dict]]:
        """把消息流切成「回合」：assistant 消息 + 其后的 tool/user 消息，直到下一条 assistant。

        这样保证截断的粒度是"完整回合"，不会切散工具调用对。
        """
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
        """★核心：从尾部（最新）向前保留尽量多的回合，直到预算上限。"""
        kept, used = [], _size(self.system)
        for turn in reversed(self._turns()):
            cost = sum(_size(m) for m in turn)
            if used + cost > self.char_budget and kept:  # 至少保留最新一回合
                break
            kept = turn + kept
            used += cost
        return [self.system] + kept

    def stats(self) -> dict:
        return {"total_msgs": len(self.messages),
                "sent_msgs": len(self.for_llm),
                "budget_chars": self.char_budget,
                "used_chars": sum(_size(m) for m in self.for_llm)}


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：往 Buffer 里灌 6 个回合（每回合含一次工具调用，共 12 条消息），")
    print("预算设为 300 字符，观察 for_llm 怎么裁剪。\n")

    buf = MessageBuffer(system_prompt="你是计算助手", char_budget=300)
    for i in range(6):
        buf.add({"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{i}", "type": "function",
             "function": {"name": "add", "arguments": f'{{"a": {i}, "b": 1}}'}}]})
        buf.add({"role": "tool", "tool_call_id": f"c{i}", "content": "r" * 60})  # 每条工具结果 60+ 字符

    st = buf.stats()
    print(f"[统计] 共 {st['total_msgs']} 条消息，预算 {st['budget_chars']} 字符，"
          f"实际发送 {st['sent_msgs']} 条（用 {st['used_chars']} 字符）\n")

    sent = buf.for_llm
    print("[发送给模型的消息]（role / 摘要）")
    for m in sent:
        if m.get("role") == "assistant":
            print(f"  assistant tool_calls={m['tool_calls'][0]['id']}")
        elif m.get("role") == "tool":
            print(f"  tool        id={m['tool_call_id']} content=({len(m['content'])}字符)")
        else:
            print(f"  {m['role']}: {m['content'][:20]}...")

    # 断言式自检：不出现孤儿 tool 消息（面试讲清楚这条）
    ok = True
    for i, m in enumerate(sent):
        if m.get("role") == "tool":
            prev = sent[i - 1]
            if prev.get("role") != "assistant" or \
               prev.get("tool_calls", [{}])[0].get("id") != m.get("tool_call_id"):
                ok = False
                print("[FAIL] 发现孤儿的 tool 消息！")
    print(f"\n[自检] 所有 tool 消息都紧跟其 assistant 发起者：{'✅ 通过' if ok else '❌ 失败'}")

    buf.reset()
    print("\n[reset] 清空对话，仅保留 system（新一轮任务）")

    # 若配了 Key，用真实模型跑一个"一路聊下去"的场景，观察 stats 变化
    if os.getenv("LLM_API_KEY") and not os.getenv("LLM_API_KEY", "").startswith("sk-your"):
        try:
            from s03_llm_client.code import ChatClient
            chat = ChatClient()
            for q in ["问题1", "问题2", "问题3"]:
                buf.add({"role": "user", "content": q})
                resp = chat.chat(buf.for_llm)
                buf.add(resp)
                print(f"  [real] {q} -> 回复 {len(str(resp.get('content')))} 字符，"
                      f"buffer 内 {len(buf.messages)} 条")
        except Exception as e:
            print(f"  [real] 真实模型调用跳过：{e}")
    print("done")