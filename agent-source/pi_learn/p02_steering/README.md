# p02: Steering —— 用户中途插话不丢

> pi 源码对照：`agent-loop.ts` 外层循环 `getSteeringMessages()`
> 上一步：[p01 事件流](../p01_event_stream/) ｜ 下一步：[p03 并行工具](../p03_parallel_tools/)

## 问题

Agent 干活时用户又打了一句："先把上一版结论发我"。
粗暴做法：打断当前回合清空重来——浪费、断因果。
pi 的做法：**排队注入**（steering），下一轮先处理插话，再继续主线。

## 方案

```
外层 while（持续轮询）
  └─ 每轮开头：pendingMessages = getSteeringMessages()
       ├─ 有插话 → 先注入 messages → 再走正常回合
       └─ 没有 → 正常回合
```

## 原理（读 code.py）

```python
class SteeringQueue:
    def take_all(self):          # 把排队的新消息取走
        ...

# Agent 里：
pending = steering.take_all()
for m in pending:
    messages.append(m)           # 插话注入到消息流（下一轮模型就能看到）
print(f"[agent] (steering) 收到并注入：{m['content']}")
```
**不打断回合边界、不清理上下文——只是"下一轮先看你说的"。**

## 运行

```bash
python p02_steering/code.py
# [agent] 第 1 轮：进度 30%
# [agent] (steering) 收到并注入：先把上一版结论发给我
# [agent] 第 2 轮：进度 60%  （模型已经看到插话）
```

## 面试问答

**Q：steering 和实时打断的取舍？**
A：steering 保顺序（下一轮处理），适合"补充性输入"；紧急中断（stop 信号）走 aborted（p04）。pi 两者都有——按紧急程度选。

**Q：会不会插话永远不处理？**
A：外层 while 每轮都拉，压缩/长任务也轮询（pi 的注释：preparation can be long-running, pick up steering queued while it ran）——不会丢。

## 延伸

- p01：插话到达也是事件（UI 能显示"用户插话"状态）
- 对比 deepseek_learn d03 Inbox：pi 是"主循环轮询 steering"，deepseek 是"订阅式 Inbox"——同目标两种实现风格