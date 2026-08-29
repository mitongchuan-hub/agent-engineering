#!/usr/bin/env python3
"""
c07_multi_agent.py - codex_learn 第 7 步：多 Agent 分工与转场

codex 的多 agent：agent/registry.rs（注册表）+ agent/role.rs（角色）+ control.rs（转场）。
agent 可以：派生子 agent（subagent）、给它独立上下文、回收结果、控制流程。

本步重建教学版：一个"项目经理"主 agent，派发两个子 agent（Planner / Reviewer），
子 agent 在独立上下文里干活，把结果交回主 agent 决策。

核心收获（面试点）：
    1. 子 agent = 独立上下文副本 + 独立循环（不污染主上下文）
    2. 角色分工：规划者想方案、评审者挑毛病、主导者做决定
    3. 转场控制：spawn（派发）→ await（等结果）→ 继续（决定）

Usage:
    python c07_multi_agent/code.py
"""


# ---------------------------------------------------------------- 子 Agent

class SubAgent:
    """一个子 agent：有独立的 prompt 和"技能"，跑自己的小循环。"""

    def __init__(self, name: str, system: str, skill):
        self.name = name
        self.system = system
        self.skill = skill  # 一个可调用函数（模拟它的能力）

    def run(self, task: str) -> str:
        """子 agent 执行：注意它只用自己的上下文，看不到主 agent 的其他消息。"""
        print(f"    [{self.name}] 收到任务：{task[:40]}...")
        result = self.skill(task)
        print(f"    [{self.name}] 产出：{result[:52]}...")
        return result


# ---------------------------------------------------------------- 主 Agent（项目经理）

class Manager:
    """主 agent：可以派发子 agent（spawn）、等待（await）、然后自己做决定。"""

    def __init__(self):
        self.planner = SubAgent("Planner", "你负责拆解方案", self._plan_skill)
        self.reviewer = SubAgent("Reviewer", "你负责挑毛病", self._review_skill)

    def _plan_skill(self, task: str) -> str:
        return (f"方案：1)读取需求 2)设计接口 3)实现核心 4)测试 —— 针对「{task[:20]}」")

    def _review_skill(self, plan: str) -> str:
        return f"评审意见：方案缺少「异常处理与回滚」，需补充 —— 针对「{plan[:24]}」"

    def run(self, task: str) -> None:
        print(f"[Manager] 任务：{task}（可以派发子 agent）\n")

        # ① spawn：并行派发（独立上下文）
        print("[Manager] 同时派发 Planner 与 Reviewer（两个独立上下文副本）")
        plan = self.planner.run(task)

        # ② 评审（改由 reviewer 评审 planner 的结果）
        print("[Manager] 转场：把方案交给 Reviewer 评审")
        review = self.reviewer.run(plan)

        # ③ 回收与决策（主 agent 拿着结果做最终决定）
        print("\n[Manager] 汇总子 agent 结果，做最终决策")
        decision = (f"采纳方案并补充评审意见（异常处理+回滚），排期 2 天。"
                    f"\n  子agent产出：{plan}；评审：{review}")
        print("[Manager] 最终决定：", decision)


if __name__ == "__main__":
    print("演示：多 Agent（主 agent 派发子 agent，子 agent 独立上下文）\n")
    Manager().run("给订单系统增加退款功能")

    print("""
[结论] 多 Agent 的价值：
       1. 上下文隔离：子 agent 各看各的，不被主对话污染
       2. 并行与成本分层：可以同时派多个，也可以便宜模型干轻活（claude 的 haiku/sonnet 思路）
       3. codex 的 control.rs 控制"什么时候转场"：子 agent 完成→结果回传→主 agent 决定
       4. deepseek-harness 更进一步：支持子 agent 协议兼容层（借用 claude/codex 的子代理）""")