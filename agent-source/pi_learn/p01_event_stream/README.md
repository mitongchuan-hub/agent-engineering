# p01: 事件流 —— Agent 的全过程变成事件

> pi 源码对照：`agent/src/agent-loop.ts`（emit 十几种事件）+ `harness/events.ts`
> 上一步：无（pi_learn 第一课）｜ 下一步：[p02 steering](../p02_steering/)

## 问题

控制台日志、进度条、遥测都在"观察 Agent"，但各写各的 hook：
加一个新 UI 要改 Agent 核心。**核心和观察者应该解耦。**

## 方案：EventBus（发布订阅）

```
Agent（emit）→ EventBus → 订阅者们
   agent_start / turn_start / message_start / message_end
   tool_call / tool_result / turn_end / agent_end
   （每个订阅者只关心自己需要的）
```

## 原理（读 code.py）

```python
class EventBus:
    def on(self, event, fn): ...      # 订阅
    def emit(self, event, payload):
        for fn in self._subs.get(event, []):
            fn(payload)               # 广播

# 订阅者：控制台日志 / 进度统计 —— 各自独立注册
console_logger(bus); progress_tracker(bus)
```

**关键设计**：Agent 只 `emit`，不知道谁在听。加 UI、加遥测、加评测打点
都不碰核心——这就是可观测性的正确打开方式。

## 运行

```bash
python p01_event_stream/code.py
# [log:agent_start] 开始任务...
# [log:tool_result] ...
# [stats] 工具调用 2 次，累计耗时 0.5s，回合 1 轮
```

## 自测问答

**Q：事件流 vs 直接函数回调？**
A：事件是"广播"（一个事件多个订阅者，互不干扰）；回调是"直连"（耦合）。多观察者、随时增删的场合事件流更干净。

**Q：事件即数据源？**
A：是。pi 的事件序列可直接用于：调试回放（把事件重演一遍看 UI）、评测（数 tool 调用/耗时）、成本统计。我们评测集（learn-mini-agent s06）的打点思路同源。

## 延伸

- p03：并行工具里事件轨与消息轨分离——事件流的进阶用法
- 对比 learn-mini-agent s01 的 print 调试：print 是一次性的，事件是可持续的