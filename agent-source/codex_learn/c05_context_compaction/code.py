#!/usr/bin/env python3
"""
c05_context_compaction.py - codex_learn 第 5 步：上下文压缩

s04（learn-mini-agent）教窗口截断；codex 更进一步：**压缩**。
对应源码：compact.rs（30KB）+ compact_model_fallback.rs

codex 的做法（我们重建教学版）：
    触发：token 预算超限
    PreCompactHook   压缩前（可拦截/自定义策略）
       └─ 用 LLM 把旧对话压成一段 CompactionSummary
    PostCompactHook  压缩后（校验/记录）
    兜底：主模型不可用 -> 换便宜模型压缩（compact_model_fallback）

本步用"规则摘要器"模拟 LLM 压缩（不联网），演示完整的压缩生命周期。

Usage:
    python c05_context_compaction/code.py
"""

import json
from typing import List, Optional


# ---------------------------------------------------------------- 消息 + 预算

def size(msg: dict) -> int:
    return len(json.dumps(msg, ensure_ascii=False))


class Context:
    def __init__(self, budget: int = 800):
        self.budget = budget
        self.system = {"role": "system", "content": "你是编程助手"}
        self.messages: List[dict] = []

    def used(self) -> int:
        return size(self.system) + sum(size(m) for m in self.messages)

    def over_budget(self) -> bool:
        return self.used() > self.budget


# ---------------------------------------------------------------- 压缩器（模拟 LLM）

class Summarizer:
    """"规则摘要器"：模拟 LLM 压缩（真实版是调小模型生成摘要）。"""

    def summarize(self, messages: List[dict]) -> str:
        n_tool = sum(1 for m in messages if m["role"] == "tool")
        n_qa = sum(1 for m in messages if m["role"] == "assistant"
                   and not m.get("tool_calls"))
        text = [m.get("content") or "" for m in messages if m.get("content")][:6]
        return (f"[摘要] 对话共 {len(messages)} 条消息：{n_qa} 轮问答、{n_tool} 次工具调用。"
                f"关键内容：{'；'.join(x[:24] for x in text)}…")


# ---------------------------------------------------------------- 压缩生命周期（带 Hook）

class Compactor:
    """压缩器：PreHook -> 摘要 -> PostHook，事件全程可观测。"""

    def __init__(self, summarizer: Summarizer, keep_latest: int = 4):
        self.summarizer = summarizer
        self.keep_latest = keep_latest
        self.hook_log: List[str] = []

    def compact(self, ctx: Context):
        """把除 system+最新几条以外的消息压成摘要。"""
        self.hook_log.append("[PreCompactHook] 触发压缩，当前使用量 "
                             f"{ctx.used()}/{ctx.budget} 字符")

        if ctx.used() <= ctx.budget:          # 没超限就不压（触发条件）
            self.hook_log.append("[PreCompactHook] 未超限，跳过")
            return False

        old = ctx.messages[: -self.keep_latest] if self.keep_latest else ctx.messages[:]
        latest = ctx.messages[-self.keep_latest:] if self.keep_latest else []
        summary = self.summarizer.summarize(old)

        # 摘要 + 保留的最新消息 => 重建上下文（模拟 model fallback：换小模型压缩）
        ctx.messages = [{"role": "user",
                         "content": f"（压缩记录）{summary} 以上为历史摘要，继续任务。"}] + latest

        self.hook_log.append("[PostCompactHook] 压缩完成："
                             f"{len(old)} 条 -> 1 条摘要，现在使用量 {ctx.used()}/{ctx.budget} 字符")
        return True


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：带 Hook 的上下文压缩（codex compact.rs 的教学版）\n")
    ctx = Context(budget=800)
    compactor = Compactor(Summarizer())

    # 制造长对话：8 轮带工具调用的消息
    for i in range(8):
        ctx.messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{i}", "type": "function",
             "function": {"name": "fetch", "arguments": '{"query": "%s"}' % ("x" * 40)}}]})
        ctx.messages.append({"role": "tool", "tool_call_id": f"c{i}",
                             "content": "结果" + "y" * 40})

    print(f"压缩前：{len(ctx.messages)} 条消息，{ctx.used()}/{ctx.budget} 字符\n")

    for step in range(3):   # 模拟继续对话又超限 → 再次压缩
        if compactor.compact(ctx):
            for log in compactor.hook_log[-2:]:
                print("  " + log)
            print(f"  压缩后：{len(ctx.messages)} 条消息")
            # 再塞 2 轮让对话继续长大
            ctx.messages.append({"role": "user", "content": "继续" + "z" * 60})
            ctx.messages.append({"role": "assistant", "content": "好的" + "w" * 40})
        else:
            break
        print()

    print("""
[结论] 压缩 vs s04 截断：截断是"丢"，压缩是"沉淀成摘要再丢"——
       信息密度不损失太多，还能继续推理。
       codex 的 Hook 机制（Pre/Post）让压缩可观测、可干预；
       model fallback 保证即使主模型挂了也能用便宜模型完成压缩。""")