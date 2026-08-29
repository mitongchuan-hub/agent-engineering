#!/usr/bin/env python3
"""
p03_parallel_tools.py - pi_learn 第 3 步：并行工具 + 双轨事件

pi 的 ToolExecutionMode 定义（types.ts）：
    sequential: 工具一个个来
    parallel:   prepare 串行 → execute 并发
       - tool_execution_end 事件按【完成顺序】发
       - tool-result 消息按【发起顺序】落位

双轨制是 pi 的精细之处：事件（给 UI：谁先完成）和消息（给模型：按发起序）
分离。codex c02 我们做了消息保序；这步加上"事件双轨"。

面试点：
    1. 并行执行，但模型看到的因果链仍按发起顺序
    2. UI 想显示"最快完成的"，按事件；模型要因果，按消息——各取所需

Usage:
    python p03_parallel_tools/code.py
"""

import concurrent.futures
import json
import time
from typing import List


def fake_call(name: str, delay: float) -> dict:
    time.sleep(delay)
    return {"name": name, "delay": delay, "value": delay * 100}


class ParallelRunner:
    """两阶段并行 + 双轨（事件按完成序 / 消息按发起序）。"""

    def __init__(self):
        self.events: List[dict] = []        # 轨道1：执行事件（完成序）

    def run(self, calls: List[dict]) -> List[str]:
        """calls: [{"name", "delay"}...]；返回按发起序的结果消息。"""
        results: dict = {}                  # index -> message
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {}
            for i, c in enumerate(calls):
                futures[pool.submit(fake_call, c["name"], c["delay"])] = i
            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                r = fut.result()
                # 轨道1：事件，严格按【完成顺序】记录 + 立即广播
                self.events.append({"index": idx, "name": r["name"],
                                    "finished_at": round(time.time(), 3)})
        # 轨道2：消息，按【发起顺序】组装
        return [json.dumps({"name": calls[i]["name"], "result": "done"},
                           ensure_ascii=False) for i in range(len(calls))]


if __name__ == "__main__":
    print("演示：并行工具执行的【双轨制】\n")
    calls = [
        {"name": "fetch_weather", "delay": 0.8},   # 慢：发起第 0 位
        {"name": "fetch_stats", "delay": 0.2},     # 快：发起第 1 位
        {"name": "search", "delay": 0.5},          # 中：发起第 2 位
    ]

    runner = ParallelRunner()
    msgs = runner.run(calls)

    print("轨道 1｜事件流（按完成顺序——给 UI/进度显示）：")
    for e in runner.events:
        print(f"    finished: {e['name']:16} (发起位 {e['index']})")

    print("\n轨道 2｜消息流（按发起顺序——给模型保持因果）：")
    for i, m in enumerate(msgs):
        print(f"    msg@{i}: {m[:40]}")

    print("""
[结论] 双轨的意义：
       UI 想知道"哪个先跑完"（进度条）→ 看事件轨
       模型想知道"我按什么顺序请求的"（因果链）→ 看消息轨
       两者分离，并行才不破坏顺序逻辑——这是 pi/codex 设计里最一致的一处。
       （codex c02 只有消息保序；pi 的事件轨是平台/UI 层的额外收益）""")