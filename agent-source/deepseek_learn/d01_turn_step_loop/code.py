#!/usr/bin/env python3
"""
d01_turn_step_loop.py - deepseek_learn 第 1 步：turn/step 状态机

对应源码：packages/core/agent-loop/src/agent.ts
对比 learn-mini-agent s01 的"双层 while"：

    pi/教学版：while (hasMoreToolCalls) { 调模型 -> 执行工具 -> 回填 }
    deepseek ：显式状态机：turn（一整轮任务）内套 step（一次模型+工具）循环，
               每个 turn/step 都记 session 日志、可被插件拦截。

状态机（面试画板）：
    IDLE ──kick──▶ RUNNING ──turn()──▶ turn+1
                       │  step+1: preStep → step → 日志
                       ▼
                   turn 结束 → IDLE（等待下次唤醒）
                   （失败 → turn/end reason=error，但不崩，等下次 kick）

本步重建：Phase 状态机（idle/running）+ turn/step 计数 + 会话日志。

Usage:
    python d01_turn_step_loop/code.py
"""

from enum import Enum


class Phase(Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"


class AgentFSM:
    """turn/step 两级状态机的教学版。"""

    def __init__(self, name: str = "agent"):
        self.name = name
        self.phase = Phase.IDLE
        self.turn_no = 0   # turn 计数（属性名避开 turn() 方法）
        self.step = 0
        self.log: list = []           # 会话日志（对应 deepseek 的 session.append）

    # ---------- 生命周期 ----------

    def kick(self):
        """driver 唤醒（对应 while (await this.turn()) {} 的入口）。"""
        if self.phase is not Phase.IDLE:
            raise RuntimeError(f"{self.name}: 只能在 IDLE 时 kick")
        self.phase = Phase.RUNNING
        self._log("kick", {"phase": "running"})
        while self.turn():
            pass  # 一个 turn 结束还有消息就继续（这里教学版只模拟一个 turn）
        self.phase = Phase.IDLE if self.phase is not Phase.DONE else Phase.DONE
        self._log("kick-end", {"phase": self.phase.value})

    def turn(self) -> bool:
        """一个 turn：推进 turn 计数，内部跑若干 step。"""
        self.turn_no += 1
        self._log("turn/start", {"turn": self.turn_no})
        turn_end = None
        while True:
            self.step += 1
            decision = self._pre_step()
            if decision == "reject":          # 插件可拒绝（d02 会展开）
                turn_end = "blocked"
                break
            if decision == "empty" and self.step == 1:
                turn_end = "completed"        # 无消息可做 = 完成
                break
            self._log("step/start", {"turn": self.turn_no, "step": self.step})
            outcome = self._step()
            self._log("step/end", {"turn": self.turn_no, "step": self.step,
                                   "outcome": outcome})
            if outcome in ("max-tokens", "error"):
                turn_end = outcome
                break
            # 教学简化：默认一轮 step 后 turn 结束
            turn_end = "completed"
            break
        self.phase = Phase.DONE if turn_end in ("error", "max-tokens") else self.phase
        self._log("turn/end", {"turn": self.turn_no, "reason": turn_end})
        return False   # 教学版：单个 turn

    # ---------- 内部（模拟一次模型调用 + 工具执行） ----------

    def _pre_step(self):
        self._log("agent/pre-step", {"turn": self.turn_no, "step": self.step})
        return "enter"   # deepseek 这里会是 dispatch.waterfall（d02）

    def _step(self):
        # 模拟：模型请求了工具 -> 执行 -> 回填（教学版直接成功）
        self._log("model/tool-call", {"tool": "compute_match"})
        self._log("tool/result", {"chars": 120})
        return "completed"

    def _log(self, event: str, data: dict):
        self.log.append({"event": event, **data})


if __name__ == "__main__":
    print("演示：turn/step 状态机 + 会话日志\n")
    fsm = AgentFSM("demo")
    fsm.kick()
    print(f"最终状态：{fsm.phase.value}（turn={fsm.turn_no}, step={fsm.step}）\n")
    print("会话日志（对应 deepseek 的 session.append 事件流）：")
    for e in fsm.log:
        print(f"  [{e.pop('event'):18}] {e}")

    print("""
[结论] 状态机 vs 双层 while：
       双层 while 管"有没有工具调用"；状态机多管两层——
       ① turn/step 两级粒度（可分别统计、可分别钩子）
       ② 全程会话日志（turn/start → step/start → step/end → turn/end）
       这些是"可观测、可插拔"的根基（d02 的钩子就挂在 pre-step 上）。""")