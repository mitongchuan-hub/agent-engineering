#!/usr/bin/env python3
"""
d03_inbox.py - deepseek_learn 第 3 步：Inbox 消息领取

deepseek 的 agent 不是"收到消息就处理"，而是有收件箱（Inbox）：
    - next-turn 队列：下一次任务是新一轮 turn
    - next-step 队列：当前 turn 内追加的步骤（用户插话/子agent唤醒）
    - claim()：按 target 领取消息；没有就”睡着“（不会被阻塞）

对应源码：packages/core/agent-loop（agent.ts 里 inbox.claim / wakeDriver / whenIdle）

面试点（和普通 while 循环比）：
    1. 解耦："谁发消息"和"agent 什么时候处理"分开 —— 并发友好
    2. 唤醒：有消息才醒（whenIdle + wake），不空转轮询
    3. 边界：step 与 turn 的领取目标不同，控制"插话"粒度

本步重建：Inbox（两个队列）+ claim + 唤醒协作。

Usage:
    python d03_inbox/code.py
"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Inbox:
    """收件箱：next-turn 与 next-step 两个队列。"""

    next_turn: deque = field(default_factory=deque)
    next_step: deque = field(default_factory=deque)
    _woken = False

    def post(self, target: str, msg: dict) -> None:
        """投递消息。target: 'next-turn' 新任务 / 'next-step' 插话。"""
        q = self.next_turn if target == "next-turn" else self.next_step
        q.append(msg)
        self._woken = True          # 唤醒标记（对应 wakeDriver）

    def claim(self, target: str, turn: int) -> list:
        """按 target 领取。turn 参数用于防御：上一个 turn 的残留不领。"""
        if target == "next-turn":
            out = list(self.next_turn)
            self.next_turn.clear()
            return out
        return [self.next_step.popleft()] if self.next_step else []

    @property
    def has_pending(self) -> bool:
        return bool(self.next_turn) or bool(self.next_step)


@dataclass
class Agent:
    """极简 Agent：等待唤醒 -> claim -> 处理。"""

    name: str
    inbox: Inbox = field(default_factory=Inbox)
    turn: int = 0

    def when_idle(self):
        """模拟"睡着"；被唤醒后处理。真实 loop 里是 while(turn())。"""
        while self.inbox.has_pending:
            self.work()

    def work(self) -> None:
        # 领 next-turn 的新任务（没有则领一步插话）
        msgs = self.inbox.claim("next-turn", self.turn)
        if msgs:
            self.turn += 1
            print(f"  [{self.name}] turn {self.turn} 开始，领取 {len(msgs)} 条任务消息")
            for m in msgs:
                print(f"     处理：{m['content'][:40]}")
        elif self.inbox.next_step:
            m = self.inbox.claim("next-step", self.turn)[0]
            print(f"  [{self.name}] 同 turn 内插话：{m['content'][:40]}")

    def wake(self, target: str, content: str) -> None:
        print(f"  [外部] post({target})：{content[:30]}...")
        self.inbox.post(target, {"role": "user", "content": content})


if __name__ == "__main__":
    print("演示：Inbox（消息投递与领取解耦）\n")
    a = Agent("demo")

    # 场景：先投两个新任务（next-turn），再在任务中途插话（next-step）
    a.wake("next-turn", "调研 MCP 协议")
    a.wake("next-turn", "写简历匹配报告")
    print("  [外部] （任务 1 进行中）插话：先把上次结论发我\n")
    a.inbox.post("next-step", {"role": "user", "content": "（插话）先总结上次结论"})

    a.when_idle()   # 唤醒并处理所有待办

    print("""
[结论] Inbox 的价值：
       1. 消息与处理解耦 → 外部（用户/子agent/定时任务）随时投递，不阻塞
       2. next-turn vs next-step → 新任务 vs 插话，粒度可控
       3. when_idle 等到有消息才醒 → 省资源、可并发唤醒
       deepseek 里 wakeDriver、AbortSignal、turn boundary 都是这套的衍生品。""")