#!/usr/bin/env python3
"""
x03_playbook.py - claude_learn 第 3 步：多 Agent 剧本（成本分层调度）

claude-code 的 code-review 命令正文就是一份"剧本"（真实片段）：
    1. Launch a haiku agent to check if the PR is reviewable
    2. Launch a sonnet agent to view the PR and summarize changes
    3. Launch 4 agents in parallel to independently review the changes

设计要点（自测点）：
    1. 成本分层：haiku（便宜快）干预检，sonnet（贵准）干重活
    2. 并行：独立评审任务并发执行，最后汇总
    3. 剧本 = 提示词里的编排，对应 codex 的"转场控制"（c07）——一个是声明式，一个是代码式

本章重建一个剧本调度器：解析简单剧本 → 分层分配 → 统计成本对比。

Usage:
    python x03_playbook/code.py
"""

import re
import threading
import time

# ---------------------------------------------------------------- 模型表

MODELS = {
    "haiku":  {"price_per_1k": 0.25,  "speed": 1.0,  "cap": "轻活（预检/摘要）"},
    "sonnet": {"price_per_1k": 3.0,   "speed": 1.6,  "cap": "重活（分析/评审）"},
}

# ---------------------------------------------------------------- 剧本解析

GRAPHS = """1. Launch a haiku agent to check if the PR is reviewable.
2. Launch a haiku agent to list relevant CLAUDE.md files.
3. Launch a sonnet agent to view the PR and summarize changes.
4. Launch 4 agents in parallel to independently review the changes."""


def parse_playbook(text: str) -> list:
    """解析为统一 [(model, task, count)] 三元组。
    单数行 -> (模型, 任务, 1)；parallel 行 -> 默认 sonnet 层，N 个并发。"""
    steps = []
    for line in text.strip().splitlines():
        m_par = re.match(r"\d+\. Launch (\d+) agents in parallel to (.+)\.?$", line)
        m_launch = re.search(r"Launch (?:a|an) (\w+) agent to (.+)\.?$", line)
        if m_par:
            steps.append(("sonnet", m_par.group(2), int(m_par.group(1))))
        elif m_launch:
            steps.append((m_launch.group(1), m_launch.group(2), 1))
    return steps


# ---------------------------------------------------------------- 调度执行

def execute_step(model: str, task: str) -> dict:
    """模拟一个 agent 干活：耗时 ∝ 模型 speed，输出 token ∝ 任务长度。"""
    time.sleep(0.15 * MODELS[model]["speed"])
    tokens = max(50, len(task) * 4)
    return {"model": model, "tokens": tokens, "cost": tokens / 1000 * MODELS[model]["price_per_1k"]}


def run(parallel: bool = True) -> dict:
    """跑完整剧本，统计成本。"""
    steps = parse_playbook(GRAPHS)
    total_cost = 0.0
    total_tokens = 0
    for model, task, cnt in steps:
        if parallel and cnt > 1:
            results = []
            threads = []
            for _ in range(cnt):
                th = threading.Thread(target=lambda: results.append(execute_step(model, task)))
                threads.append(th); th.start()
            for th in threads:
                th.join()
        else:
            results = [execute_step(model, task) for _ in range(cnt)]
        for r in results:
            total_tokens += r["tokens"]
            total_cost += r["cost"]
        print(f"  {model:6} ×{cnt:2}  {task[:38]:38} "
              f"cost≈${results[0]['cost']:.4f}（{MODELS[model]['cap']}）")
    return {"cost": total_cost, "tokens": total_tokens}


if __name__ == "__main__":
    print("演示：成本分层调度（真剧本：haiku 轻活 + sonnet 重活 + 并行评审）\n")
    layered = run(parallel=True)

    # 对比：全用 sonnet（贵）跑同样的剧本
    print("\n[对比] 若全部强上 sonnet（不看分层）：")
    MODELS_SAVE = MODELS.copy()
    MODELS["haiku"] = dict(MODELS["sonnet"])   # 强制同价
    all_expensive = run(parallel=True)
    MODELS.clear(); MODELS.update(MODELS_SAVE)

    print(f"\n分层成本  : ${layered['cost']:.3f}（{layered['tokens']} tok）")
    print(f"全贵成本  : ${all_expensive['cost']:.3f}（{all_expensive['tokens']} tok）")
    print(f"节省      : {1 - layered['cost']/all_expensive['cost']:.0%}\n")
    print("[结论] 分层 = 便宜模型趟量大的活，贵模型只啃硬骨头，成本立省一大截。")