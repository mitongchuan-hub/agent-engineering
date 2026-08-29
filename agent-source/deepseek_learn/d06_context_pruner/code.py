#!/usr/bin/env python3
"""
d06_context_pruner.py - deepseek_learn 第 6 步：上下文裁剪压缩

deepseek 的 compaction 包比 codex 多一个耐人寻味的组件：
    compaction-tool-result-pruner —— 专门裁剪「工具结果」。
为什么单列？因为工具结果往往又长又重复（list 输出、日志、大 JSON），
但其中只有一小部分是模型后续要用到的。

本步重建：
    ① 工具结果裁剪器（pruner）：按类型策略压缩长结果
    ② 摘要压缩（沿用 codex c05 概念，做成 deepseek 版管线）
    ③ 触发阈值 + 结果回填

面试点：上下文压缩有两个抓手——消息历史（删/摘要）和工具结果（裁剪），
后者开销更小（不需要 LLM），先剪再加。

Usage:
    python d06_context_pruner/code.py
"""

import json
import re
from typing import List


# ---------------------------------------------------------------- Pruner（裁剪工具结果）

class ToolResultPruner:
    """按工具输出类型做裁剪（深度对应 compaction-tool-result-pruner）。"""

    MAX_KEEP = 300          # 保留上限字符
    KEEP_HEAD = 150         # 保留头部
    KEEP_TAIL = 100         # 保留尾部

    def prune(self, tool_name: str, raw: str) -> dict:
        """返回 {kept, dropped, summary}。"""
        if len(raw) <= self.MAX_KEEP:
            return {"kept": raw, "dropped": 0, "summary": raw}

        # ① 结构化输出（JSON）：保留骨架（键名 + 数组长度）
        shape = self._shape(raw)
        head = raw[: self.KEEP_HEAD]
        tail = raw[-self.KEEP_TAIL:]
        return {
            "kept": head + f"\n…[中间 {len(raw) - self.KEEP_HEAD - self.KEEP_TAIL} 字符已裁剪]…" + tail,
            "dropped": len(raw) - self.KEEP_HEAD - self.KEEP_TAIL,
            "summary": shape,
        }

    def _shape(self, raw: str) -> str:
        """JSON 结构化摘要：{键: 类型[, 数组长度N]}。"""
        try:
            obj = json.loads(raw)
        except Exception:
            return f"text[{len(raw)}chars]"
        if isinstance(obj, list):
            return f"array[{len(obj)}]"
        if isinstance(obj, dict):
            parts = []
            for k, v in list(obj.items())[:6]:
                parts.append(f"{k}: {type(v).__name__}"
                             + (f"[{len(v)}]" if isinstance(v, (list, dict)) else ""))
            return "{" + ", ".join(parts) + "}"
        return f"{type(obj).__name__}"


# ---------------------------------------------------------------- 历史压缩（摘要）

class HistoryCompactor:
    """旧对话压缩成摘要（对比 codex c05：这里强调"代价更小的先做"）。"""

    def compact(self, messages: List[dict], keep_latest: int = 2) -> List[dict]:
        old, latest = messages[: -keep_latest], messages[-keep_latest:]
        if not old:
            return messages
        summary = (f"[历史摘要] {len(old)} 条消息，含 "
                   f"{sum(1 for m in old if m.get('role') == 'tool')} 次工具调用、"
                   f"{sum(1 for m in old if m.get('content'))} 条文本")
        return [{"role": "user", "content": f"（{summary}，继续任务）"}] + latest


# ---------------------------------------------------------------- 完整管线

def pipeline(messages: List[dict], budget: int = 1200) -> dict:
    """pruner（工具结果）先行 -> 仍超限再历史压缩。"""
    total = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    if total <= budget:
        return {"action": "none", "messages": messages, "used": total, "budget": budget}

    # ① 先裁剪工具结果（零 LLM 成本）
    steps = 0
    for m in messages:
        if m.get("role") == "tool" and m.get("content"):
            r = ToolResultPruner().prune("tool", m["content"])
            if r["dropped"]:
                m["content"] = r["kept"]
                steps += 1
    after = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)

    # ② 仍超限：历史摘要（需要一次小模型调用，成本更高，后做）
    action = f"pruned:{steps}"
    if after > budget:
        messages = HistoryCompactor().compact(messages, keep_latest=2)
        after = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        action += "+compacted"
    return {"action": action, "messages": messages, "used": after, "budget": budget}


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：两级压缩（先剪工具结果，再压历史）\n")

    # 造一段超长对话：2 轮 + 一个 1500 字符的工具结果
    msgs = [
        {"role": "user", "content": "查一下有哪些任务"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "t1", "type": "function",
             "function": {"name": "list_tasks", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "t1",
         "content": json.dumps({"tasks": [{"id": i, "name": f"任务{i:03d}",
                                           "desc": "详情" * 20} for i in range(20)]})},
        {"role": "assistant", "content": "好的，我看到了 20 个任务，下面逐个分析：" + "字" * 50},
        {"role": "user", "content": "继续"},
    ]
    r = pipeline(msgs, budget=900)
    print(f"动作：{r['action']} ｜ 用量 {r['used']}/{r['budget']}")
    print(f"最终消息条数：{len(r['messages'])}")
    print("\n裁剪后的工具结果（前 120 字符）：")
    print(" ", r["messages"][2]["content"][:170] + "…")

    print("""
[结论] 两级压缩的优先级（面试背出来）：
       1. 先剪工具结果：零成本、立竿见影（大 JSON 裁剪 70%+ 是常态）
       2. 再压消息历史：需要一次小模型调用，最后手段
       3. 最后才考虑截断丢信息：绝不优先
       deepseek 单列 compaction-tool-result-pruner，就是因为第一步最划算。""")