# 第 06 章：Steering 与 Follow-up 队列

## 本章问题

Agent 运行期间可能出现两种新增消息：

- **Steering**：用户在 Agent 工作时临时改变方向，应尽快插入下一次模型请求。
- **Follow-up**：用户追加的后续任务，应等 Agent 当前工作自然结束后再处理。

它们不能共用一个简单列表，因为注入时机不同。

## 源码调用链

```text
Agent.steer()      -> steeringQueue.enqueue()
Agent.followUp()   -> followUpQueue.enqueue()

runLoop()
  -> 初始 drain steering
  -> 当前 turn 完成后 drain steering
  -> 只要有 tool call 或 pending steering，继续当前内循环
  -> 内循环自然结束后才 drain follow-up
  -> follow-up 存在则进入下一轮外循环
```

Pi 的 `PendingMessageQueue` 只有一个很小但关键的策略：

- `all`：一次 drain 全部消息。
- `one-at-a-time`：一次只取最老的一条。

## 最小实现

本章的 `run_queue_loop()` 保留 Pi 的循环边界，但把模型和工具简化为脚本对象：

```python
pending = steering_queue.drain()
# 当前 assistant 的 tool calls 先完成
pending = steering_queue.drain()
# 没有 tool call 和 steering 后，才看 follow-up
pending = follow_up_queue.drain()
```

这解释了一个容易写错的行为：steering 不会取消当前 assistant 已经返回的工具调用。它只能在工具结果处理完后进入下一次模型请求。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s06_message_queues/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s06_message_queues.py
```

示例使用 `one-at-a-time`：两条 steering 消息分别触发后续 turn，follow-up 则在 steering 和当前工作都结束后才出现。

## 关键测试

- `all` 和 `one-at-a-time` 的 drain 行为。
- 初始 steering 在第一次 Provider 请求前注入。
- one-at-a-time 每条消息最多占一个后续 turn。
- 当前 tool call 完成前不会注入 steering。
- follow-up 只在 Agent 原本要停止时触发。
- follow-up 会等待剩余工具轮次完成。
- steering 优先于 follow-up。
- `prepareNextTurn` 在下一轮开始前执行。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| 模型响应使用脚本列表 | Pi 通过真实 `AgentLoopConfig` 轮询 Provider |
| 工具结果是自动生成的字符串 | Pi 运行完整工具准备、并发和事件流水线 |
| 只模拟消息注入边界 | Pi 的 Agent 还提供公开 `steer`、`followUp` 和清理 API |
| 不处理 continuation | Pi 的 `continue()` 还会处理 assistant 尾部的队列优先级 |

abort、terminate、settled 和失败清理留到第 07 章。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent.ts)：`PendingMessageQueue`、`steer`、`followUp`、`createLoopConfig`。
- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`runLoop` 内层工具/steering 循环和外层 follow-up 循环。
- [`agent.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent.test.ts)：steering、follow-up 和 continuation 队列测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 07 章处理运行控制边界：abort、错误、terminate、`agent_end` 和真正的 `agent_settled` 为什么不能混为一谈。
