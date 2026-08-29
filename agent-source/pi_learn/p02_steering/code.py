#!/usr/bin/env python3
"""
p02_steering.py - pi_learn 第 2 步：steering 消息（用户中途插话）

pi 的 agent-loop.ts 外层 while 里有个细节：
    pendingMessages = config.getSteeringMessages()   // 用户排队的新消息

意义：Agent 正在干活时用户又发了一条消息——
不是"打断/清空"，而是**排队注入下一轮**，任务上下文不乱。

对应源码：agent-loop.ts 的 steering 逻辑（外层 while + 内层处理后轮询）。

本步重建：
    ① 长任务进行中，用户插话（steering 消息入队）
    ② 下一轮先从队列取插话，注入 messages 再继续
    ③ 对比"打断即清空"的坏行为

面试点：steering = 让"人机协作"顺滑：不打断因果链，但即时生效。

Usage:
    python p02_steering/code.py
"""

import time
from collections import deque


class SteeringQueue:
    """steering 消息队列（对应 getSteeringMessages）。"""

    def __init__(self):
        self._q: deque = deque()

    def push(self, content: str) -> None:
        self._q.append({"role": "user", "content": content})

    def take_all(self) -> list:
        out = list(self._q)
        self._q.clear()
        return out

    @property
    def empty(self) -> bool:
        return not self._q


class BusyAgent:
    """在长任务里处理 steering 消息的 Agent。"""

    def __init__(self, steering: SteeringQueue):
        self.steering = steering

    def run(self, task: str) -> None:
        messages = [{"role": "user", "content": task}]
        print(f"[agent] 任务开始：{task}")
        has_more = True
        pending = []

        outer = 0
        while has_more or pending:
            outer += 1
            # ① 处理队列里新到的 steering（每轮只取，配合持续轮询）
            if not pending and not self.steering.empty:
                pending = self.steering.take_all()
                for m in pending:
                    messages.append(m)
                    print(f"[agent] (steering) 收到并注入：{m['content']}")
                pending = []

            # ② 模拟模型一轮干活：查天气 -> 【中间模拟耗时】-> 总结
            time.sleep(0.4)
            if outer == 1:
                print(f"[agent] 第 {outer} 轮：开发中…进度 30%")
                # 任务中途，用户插话进来了
                self.steering.push("先把上一版结论发给我")
            elif outer == 2:
                print(f"[agent] 第 {outer} 轮：开发中…进度 60%")
            else:
                print(f"[agent] 第 {outer} 轮：完成开发")
                has_more = False

        print(f"\n[agent] 最终 messages 顺序（含插话注入点）：")
        for m in messages:
            print(f"    [{m['role']}] {m['content'][:30]}")


if __name__ == "__main__":
    print("演示：steering 消息（用户中途插话排队注入，不打断因果）\n")
    sq = SteeringQueue()
    BusyAgent(sq).run("开发订单模块（预计 3 轮）")

    print("""
[结论] steering vs 中断（对比记忆点）：
       中断：清掉上下文重来 —— 浪费、断因果
       steering：排队进下一轮 —— 即时生效又保上下文顺序
       pi 里它还支持更细：pendingMessages 每轮都查（getSteeringMessages），
       长压缩/准备期间也不丢失用户输入。""")