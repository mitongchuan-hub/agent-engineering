#!/usr/bin/env python3
"""
c02_parallel_tools.py - codex_learn 第 2 步：工具并行执行

模型一次可能请求多个工具调用（比如同时查两个城市的天气）。
串行执行慢；全部同时跑又可能乱序。codex 原版：tools/parallel.rs
pi 的 types.ts 里也是同一思路："prepare 串行 -> execute 并发 -> 回填保序"。

这一章重建两阶段并行：

    阶段1 prepare（串行）：校验参数、准备执行环境 —— 快速，出错早发现
    阶段2 execute（并发）：真正干活的耗时操作 —— 用线程池，互不阻塞
    回填顺序：tool 消息按「模型发起顺序」排列，不乱因果

核心收获（面试点）：
    1. 并发 ≠ 乱序：结果消息顺序必须跟模型请求顺序一致
    2. 两阶段的意义：校验放串行（便宜），执行放并行（贵但快）
    3. 线程安全：每个工具是独立函数调用，天然可并发

Usage:
    python c02_parallel_tools/code.py
"""

import concurrent.futures
import json
import time
from typing import List


# ---------------------------------------------------------------- 工具

# 模拟的"慢"工具：耗时操作（如等待外部 API）
def fetch_weather(city: str, delay: float = 0.8) -> dict:
    time.sleep(delay)  # 模拟网络等待
    return {"city": city, "temp": 25 + len(city) % 8, "delay": delay}


def fetch_stats(name: str, delay: float = 0.6) -> dict:
    time.sleep(delay)
    return {"name": name, "value": len(name) * 10, "delay": delay}


# 工具注册表：name -> (func, arg_names)
TOOL_TABLE = {
    "fetch_weather": (fetch_weather, ["city"]),
    "fetch_stats": (fetch_stats, ["name"]),
}


# ---------------------------------------------------------------- 两阶段执行器

class ParallelExecutor:
    """两阶段并行执行：prepare 串行 -> execute 并发 -> 回填保序。"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def execute_many(self, calls: List[dict]) -> List[str]:
        """calls: [{"name", "arguments(json str)"}...]  按发起顺序返回结果字符串。"""
        # ---------- 阶段 1：prepare（串行、便宜、早失败） ----------
        prepared = []
        for c in calls:
            name = c["name"]
            if name not in TOOL_TABLE:
                prepared.append({"name": name, "args": None, "error": f"未知工具 {name}"})
                continue
            try:
                args = json.loads(c["arguments"])
                prepared.append({"name": name, "args": args, "error": None})
            except Exception as e:
                prepared.append({"name": name, "args": None, "error": f"参数错误: {e}"})

        # ---------- 阶段 2：execute（并发、贵但快） ----------
        results: dict = {}  # index -> result（并发写入，最后按 index 排回）
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for i, p in enumerate(prepared):
                if p["error"]:
                    results[i] = p["error"]  # prepare 失败的不执行
                    continue
                func, _ = TOOL_TABLE[p["name"]]
                futures[pool.submit(func, **p["args"])] = i
            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = json.dumps(fut.result(), ensure_ascii=False)
                except Exception as e:  # 执行异常也不炸整体
                    results[idx] = f"执行失败: {type(e).__name__}: {e}"

        # ---------- 回填：按发起顺序（保序！） ----------
        return [results[i] for i in range(len(prepared))]


# ---------------------------------------------------------------- Agent（简版）

class DemoLLM:
    """脚本模型：一次请求 3 个并行工具，下一轮收尾。"""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            calls = [
                {"name": "fetch_weather", "arguments": json.dumps({"city": "北京"})},
                {"name": "fetch_stats", "arguments": json.dumps({"name": "cpu"})},
                {"name": "fetch_weather", "arguments": json.dumps({"city": "杭州"})},
            ]
            return {"role": "assistant", "content": None,
                    "tool_calls": [{"id": f"c{i}", "type": "function",
                                    "function": c} for i, c in enumerate(calls)]}
        return {"role": "assistant", "content": "三个查询都拿到了。", "tool_calls": None}


def run(ex: ParallelExecutor) -> None:
    llm = DemoLLM()
    messages = [{"role": "user", "content": "并行查三个数据"}]
    for step in range(1, 5):
        resp = llm.chat(messages)
        messages.append(resp)
        calls = resp.get("tool_calls") or []
        if not calls:
            print(f"[agent] step {step}: {resp['content']}")
            return
        names = [c["function"]["name"] for c in calls]
        print(f"[agent] step {step}: 模型请求 {len(calls)} 个并行调用: {names}")

        t0 = time.time()
        outs = ex.execute_many([c["function"] for c in calls])
        elapsed = time.time() - t0

        print(f"[agent] step {step}: 并行执行耗时 {elapsed:.2f}s")
        for c, out in zip(calls, outs):
            print(f"    - {c['function']['name']} -> {out[:60]}")
        for c, out in zip(calls, outs):
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})


if __name__ == "__main__":
    print("演示：并行工具执行（3 个慢调用，串行约 2.2s，并行约 0.9s）\n")
    run(ParallelExecutor())

    # 对比串行
    print("\n[对比] 串行执行同样 3 个调用:")
    t0 = time.time()
    fetch_weather("北京")
    fetch_stats("cpu")
    fetch_weather("杭州")
    print(f"  串行耗时：{time.time()-t0:.2f}s（并行约为其一半）\n")
    print("[结论] 两阶段：校验串行保正确、执行并发保性能、回填保序保因果。")