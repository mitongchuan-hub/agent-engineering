#!/usr/bin/env python3
"""
p01_event_stream.py - pi_learn 第 1 步：事件流

pi 的核心气质：Agent 的全过程是**一串事件**（EventStream），
订阅者（TUI/日志/进度条/遥测）各自监听自己关心的。

对应源码：packages/agent/src/agent-loop.ts（emit event）+ harness/events.ts

事件流（面试默写）：
    agent_start → turn_start → message_start → message_end
                       └─ tool_call → tool_result（可循环）
    turn_end → agent_end

本步重建：EventBus + 两个订阅者（控制台日志 / 进度统计）。

面试点：
    1. 可观测性 = 一切皆事件，UI 与核心解耦
    2. 订阅者自治：加个新 UI 不改 Agent；不加订阅者=零开销
    3. 事件即调试/回放/评测的数据源

Usage:
    python p01_event_stream/code.py
"""

import time
from typing import Callable, Dict, List


# ---------------------------------------------------------------- EventBus

class EventBus:
    """极简发布订阅：emit(type, payload) -> 所有订阅者收到。"""

    def __init__(self):
        self._subs: Dict[str, List[Callable]] = {}

    def on(self, event: str, fn: Callable) -> None:
        self._subs.setdefault(event, []).append(fn)

    def emit(self, event: str, payload: dict = None) -> None:
        for fn in self._subs.get(event, []):
            fn(payload or {})


# ---------------------------------------------------------------- 订阅者

def console_logger(bus: EventBus) -> None:
    """订阅者 1：控制台逐步日志。"""
    def log(p):
        print(f"    [log:{p.get('event','')}] {p.get('msg','')}")
    for e in ("agent_start", "message_start", "tool_result", "turn_end"):
        wrapped = lambda p, e=e, log=log: log({**p, "event": e})
        bus.on(e, wrapped)


def progress_tracker(bus: EventBus) -> None:
    """订阅者 2：统计工具调用次数与耗时（UI/遥测的简化版）。"""
    stats = {"tools": 0, "turns": 0, "elapsed": 0.0}

    def on_tool(p):
        stats["tools"] += 1
        stats["elapsed"] += p.get("cost", 0)

    def on_turn(p):
        stats["turns"] += 1

    def report(p):
        print(f"    [stats] 工具调用 {stats['tools']} 次，累计耗时 {stats['elapsed']:.1f}s，"
              f"回合 {stats['turns']} 轮")
    bus.on("tool_result", on_tool)
    bus.on("turn_end", on_turn)
    bus.on("agent_end", report)


# ---------------------------------------------------------------- Agent（事件驱动）

class EventAgent:
    def run(self, bus: EventBus, task: str) -> str:
        bus.emit("agent_start", {"msg": f"开始任务：{task}"})
        bus.emit("turn_start", {"msg": f"turn 1"})

        # 第 1 个消息（用户任务）
        bus.emit("message_start", {"msg": "user: " + task[:20]})
        bus.emit("message_end", {"msg": "（模型思考中…）"})

        # 工具调用 1
        bus.emit("tool_call", {"name": "compute_match", "args": "resume×jd"})
        time.sleep(0.3)
        bus.emit("tool_result", {"name": "compute_match", "cost": 0.3,
                                 "result": "总分 93"})

        # 工具调用 2
        bus.emit("tool_call", {"name": "read_text_file", "args": "jd.md"})
        time.sleep(0.2)
        bus.emit("tool_result", {"name": "read_text_file", "cost": 0.2,
                                 "result": "245 字符"})

        bus.emit("turn_end", {"msg": "turn 完成，模型给出总结"})
        bus.emit("agent_end", {"msg": "任务结束"})
        return "匹配完成：93 分，强烈推荐"


if __name__ == "__main__":
    print("演示：事件流（EventBus + 两个订阅者）\n")
    bus = EventBus()
    console_logger(bus)
    progress_tracker(bus)

    answer = EventAgent().run(bus, "评估简历与 AI 工程师岗匹配度")
    print(f"\n[agent] 最终回答：{answer}")
    print("""
[结论] 事件流的收益：
       1. UI（TUI 逐行动画）、日志、遥测、评测 —— 全是订阅者，核心零改动
       2. 事件序列 = 完整执行记录：调试看事件、回放看事件、评测打点也看事件
       3. pi 的 agent-loop.ts 里 emit 了十几种事件，TUI 全部消费它们""")