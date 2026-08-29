# d03: Inbox —— 消息投递与处理解耦

> deepseek 源码对照：`packages/core/agent-loop`（inbox.claim / wakeDriver / whenIdle）
> 上一步：[d02 插件钩子](../d02_plugin_hooks/) ｜ 下一步：[d04 严格 schema](../d04_strict_schema/)

## 问题

普通 while 循环的 Agent 是"拉模式"：循环里主动拿消息。但当消息来自多方
（用户打字、子 agent 汇报、定时任务、webhook），**谁负责唤醒它？什么时候处理？**

## 方案：Inbox（收件箱）

```
Producer（随便谁）        Inbox                 Agent
  用户 ──post──▶ next-turn 队列 ──claim──▶ 处理（新任务）
  子Agent ─post─▶ next-step 队列 ─claim──▶ 处理（同回合插话）
  定时器 ──post──▶                    （无消息就 when_idle 睡着）
```

## 原理（读 code.py）

### ① 两个队列 = 两种粒度

```python
def post(self, target, msg):
    q = self.next_turn if target == "next-turn" else self.next_step
    q.append(msg); self._woken = True      # 对应 wakeDriver

def claim(self, target, turn):
    if target == "next-turn":
        return 清空 next_turn              # 新任务整批处理
    return [popleft()] if next_step else []  # 插话一次一条
```
- `next-turn`：新任务（新一轮 turn）
- `next-step`：当前回合内插话（不会打断正在进行的 turn 边界）

### ② 唤醒而非轮询

```python
def when_idle(self):
    while self.inbox.has_pending:
        self.work()                        # 有消息才醒，没有就睡
```
生产实现里没有忙等：`whenIdle()` 在 `activityDone` 上 await，
被 `wakeDriver()` 显式唤醒——省资源且支持多个 Producer 并发投递。

## 运行

```bash
python d03_inbox/code.py
# [外部] post(next-turn)：调研 MCP 协议...
# [外部] post(next-turn)：写简历匹配报告...
# [外部] （任务 1 进行中）插话：先把上次结论发我
#   [demo] turn 1 开始，领取 2 条任务消息
#   [demo] 同 turn 内插话：先总结上次结论
```

## 面试问答

**Q：Inbox 的价值在哪？**
A：解耦。消息来源不关心 Agent 忙不忙；Agent 处理时也不阻塞 Producer。多 agent 协作、用户插话、调度任务都用同一套接入口。

**Q：next-turn 和 next-step 区别的意义？**
A：控制"插话粒度"。next-turn 代表新一轮任务（上下文可重置/换模型——deepseek 的 prepareNextTurn 干这个）；next-step 是当前回合内追加（不打断因果链）。

**Q：和消息队列（MQ）的关系？**
A：同一个思想，进程内简化版。生产跨进程就是 MQ（Kafka/RabbitMQ）——Agent 的 inbox 是进程内队列 + 唤醒机制。

## 延伸

- d01：turn 结束读 Inbox 决定是否继续（阻塞/唤醒）
- 对比 pi_learn p02（steering 消息）：pi 是"主循环里轮询 steering"，deepseek 是"订阅式的 Inbox"，两种风格