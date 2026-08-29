# d01: turn/step 状态机 —— 放着比 while 多管两层

> deepseek 源码对照：`packages/core/agent-loop/src/agent.ts`（21KB）
> 上一步：无（deepseek_learn 第一课）｜ 下一步：[d02 插件钩子](../d02_plugin_hooks/)

## 问题

learn-mini-agent s01 的循环足够跑通任务，但它的状态只有"进行中/结束"，
两个生产痛点：
- 一次工具调用和整个任务的粒度混在一起，**怎么分别统计/干预？**
- 想在"调模型之前"插个安全审查钩子，**往哪挂？**

## 方案：turn（回合）/ step（步骤）两级状态机

```
IDLE → kick() → RUNNING
   └─ turn()  (一整轮任务)
        └─ step 循环 (一次「模型调用+工具执行」)
             preStep → [模型调用] → 工具执行 → step/end 日志
        turn/end 日志（reason: completed/blocked/max-tokens/error）
→ 回 IDLE，等待下一次唤醒
```

## 原理（读 code.py）

### ① 状态与计数分离

```python
self.phase = Phase.IDLE / RUNNING / DONE   # 状态：能不能 kick
self.turn_no, self.step                    # 计数：第几轮第几步
```
**状态**决定"现在能不能动"；**计数**决定"统计到哪了"——职责分开。

### ② 全程会话日志（面试亮点）

```python
self._log("turn/start", {"turn": 1})
self._log("step/start", {"turn": 1, "step": 1})   # 每次模型调用前
self._log("step/end",   {"turn": 1, "step": 1, "outcome": "completed"})
self._log("turn/end",   {"turn": 1, "reason": "completed"})
```
deepseek 的 `session.append()` 就是把这些事件**持久化**了——
调试、回放、评测全靠这条日志河。

### ③ 插桩点明确

```python
def _pre_step(self):
    # deepseek 这里不是普通函数，而是 dispatch.waterfall("agent/pre-step", ...)
    return "enter"
```
pre-step 是**每一轮模型调用前必经之地**——d02 的插件链就挂在这里。

## 运行

```bash
python d01_turn_step_loop/code.py
# 会话日志：
#   [turn/start]      {"turn": 1}
#   [agent/pre-step]  {"turn": 1, "step": 1}
#   [step/start] ...
#   [tool/result] ...
#   [turn/end]        {"turn": 1, "reason": "completed"}
```

## 面试问答

**Q：状态机和"双层 while"差在哪？**
A：while 只关心"还有没有工具调用"；状态机额外提供两级粒度（turn/step）+ 全程日志 + 明确的钩子点。代价是代码更绕——所以 pi 用 while（简单），deepseek 用状态机（可插拔）。

**Q：turn/end 的 reason 有什么用？**
A：决定下一步：completed→等新任务；blocked→去读 Inbox 新消息；error→上报/重试；max-tokens→强制收尾但保留状态。这是"可观测的失败处理"（对比我们 s09 的兜底）。

**Q：什么时候该上状态机？**
A：需要插钩子、需要恢复、需要多 agent 协作时。纯单 agent 教学用 while 够了。

## 延伸

- d02：钩子挂在哪？就挂在 pre-step 这个点上
- 对比 learn-mini-agent s01（双层 while）与 pi_learn p01（事件流）