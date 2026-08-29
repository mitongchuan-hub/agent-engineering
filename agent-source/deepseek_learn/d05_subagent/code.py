#!/usr/bin/env python3
"""
d05_subagent.py - deepseek_learn 第 5 步：子 Agent 体系

deepseek 的 subagent 是整个 monorepo 里最大的组（11 个子包，114 文件）：
    subagent-in-process-driver   进程内（快，共享内存）
    subagent-fork-in-process     fork 隔离（稳，独立状态）
    subagent-claude-code         兼容 Claude Code 的子代理协议！
    subagent-codex               兼容 codex 的子代理协议！
    tool-subagent(-control/-report)  发起/控制/汇报三件套

本步重建教学版：
    ① Driver 抽象（in-process / fork 两种"运行方式"）
    ② 任务契约：每个子 agent 收 task、还 report
    ③ 主 agent 分发与汇总

面试点：
    1. 子 agent 模式 = 独立上下文 + 明确契约（task/report）
    2. 运行方式可选：in-process（快）vs fork（隔离）——工程取舍
    3. 协议兼容层（claude/codex）：别人家的 agent 也能当子代理（互操作）

Usage:
    python d05_subagent/code.py
"""

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List


# ---------------------------------------------------------------- 契约

@dataclass
class Task:
    title: str
    detail: str
    payload: dict = field(default_factory=dict)


@dataclass
class Report:
    title: str
    ok: bool
    summary: str
    data: dict = field(default_factory=dict)
    driver: str = ""


# ---------------------------------------------------------------- Driver（运行方式）

class InProcessDriver:
    """进程内 driver：同一线程池里跑，快，但共享进程状态。"""

    name = "in-process"

    def run(self, fn: Callable[[Task], Report], task: Task) -> Report:
        return fn(task)                       # 直接调用


class ForkDriver:
    """fork 模拟 driver：独立"域"（教学版用隔离线程 + 延迟演示独立）。"""

    name = "fork"
    # 模拟：fork 出独立内存域，无法访问主进程的局部状态
    NO_SHARED_STATE = True

    def run(self, fn: Callable[[Task], Report], task: Task) -> Report:
        out = {}

        def _work():
            out["report"] = fn(task)          # 在"独立"线程里执行

        t = threading.Thread(target=_work)
        t.start()
        t.join()
        report = out["report"]
        report.driver = self.name
        return report


# ---------------------------------------------------------------- 子 Agent

class SubAgent:
    """子 agent：名字 + 技能 + 可选的运行 driver。"""

    def __init__(self, name: str, skill: Callable[[Task], Report],
                 driver=None):
        self.name = name
        self.skill = skill
        self.driver = driver or InProcessDriver()

    def execute(self, task: Task) -> Report:
        t0 = time.time()
        report = self.driver.run(self.skill, task)
        print(f"  [{self.name}] ({report.driver}) 完成 {task.title}，"
              f"耗时 {time.time()-t0:.2f}s")
        return report


# ---------------------------------------------------------------- 技能实现

def analyze_skill(task: Task) -> Report:
    time.sleep(0.05)  # 模拟干活
    return Report(task.title, True,
                  f"分析完成：{task.detail[:20]}…共 {len(task.payload)} 项数据",
                  {"score": 92})


def review_skill(task: Task) -> Report:
    time.sleep(0.05)
    return Report(task.title, True, "评审通过：逻辑完整，建议补测试",
                  {"issues": []})


# ---------------------------------------------------------------- 主 Agent 编排

class Manager:
    def __init__(self):
        self.agents: Dict[str, SubAgent] = {
            "analyzer": SubAgent("analyzer", analyze_skill, InProcessDriver()),
            "reviewer": SubAgent("reviewer", review_skill, ForkDriver()),  # 隔离运行
        }

    def dispatch(self, task: Task, agent_name: str) -> Report:
        print(f"[Manager] 派发 '{task.title}' → {agent_name}")
        return self.agents[agent_name].execute(task)

    def parallel_dispatch(self, task: Task) -> List[Report]:
        """同时派多个子 agent（各用各的 driver）。"""
        print(f"[Manager] 并行派发 {list(self.agents)}")
        results = []
        threads = []
        for name, ag in self.agents.items():
            t = threading.Thread(
                target=lambda: results.append((name, ag.execute(task))))
            threads.append(t); t.start()
        for t in threads:
            t.join()
        return [r for _, r in results]


if __name__ == "__main__":
    print("演示：子 Agent 体系（契约 + Driver 抽象 + 编排）\n")
    mgr = Manager()
    task = Task("订单系统退款", "增加退款与回滚流程",
                payload={"refund": True, "rollback": True})
    reports = mgr.parallel_dispatch(task)
    print("\n[Manager] 汇总报告：")
    for r in reports:
        print(f"  - {r.title}: {r.summary}（driver={r.driver}）")

    print("""
[结论] 子 Agent 的工程要点：
       1. 契约先行：Task in / Report out —— 子 agent 是"函数"的放大版
       2. Driver 抽象：in-process（快）/ fork（隔离）/ 远程（可扩展），按需选
       3. deepseek 的杀手锏：subagent-claude-code / subagent-codex
          直接把别家 Agent 变成自己的子 agent（协议兼容层）
       4. 对比 c07（codex）：codex 的 role/control 偏"转场控制"，
          deepseek 的 subagent 偏"协议与隔离"——一个管流程，一个管边界""")