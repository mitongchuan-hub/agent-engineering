# 第 07 章：Abort、错误与结束边界

## 本章问题

Agent 的“结束”至少有三个层次：

- **turn 结束**：一次 assistant 响应和它的工具结果处理完。
- **`agent_end`**：低层 Agent Loop 不再产生新的 loop 事件。
- **`agent_settled`**：高层 AgentSession 确认没有自动重试、压缩或排队 continuation，运行真正稳定。

把这几个事件当成同一个状态，会导致 UI 提前解锁、Session 提前关闭，或恢复逻辑重复执行。

## 源码调用链

```text
Agent.prompt()
  -> runWithLifecycle()
     -> runAgentLoop()
        -> agent_end
     -> 等待 agent_end listeners
     -> finishRun()                 # Agent core idle

AgentSession._runAgentPrompt()
  -> agent.prompt()
  -> _handlePostAgentRun()
     -> retry / compaction / agent.continue
  -> _emitAgentSettled()            # Session 真正 settled
```

Pi 的核心 Agent 只定义 `agent_end`，`agent_settled` 是 `coding-agent` 的 Session 层事件。它发生在 `_handlePostAgentRun()` 返回 false 之后。

## 控制状态

| 状态/原因 | 处理 |
|---|---|
| `stop` | 当前模型轮次自然结束 |
| `error` | 生成错误 assistant；Session 可能自动重试 |
| `aborted` | 用户取消或 signal 中止；仍需正常清理和 settled |
| `length` | 输出达到上限；可能触发上下文恢复或重新尝试 |
| `terminate` | 工具 batch 请求本轮停止，不等于整个 Session settled |
| `agent_end` | 低层循环结束，不保证高层没有后处理 |
| `agent_settled` | 重试、压缩、队列 continuation 全部结束 |

## 最小实现

本章包含两个独立层次：

- `AgentCore`：维护 `is_streaming`、transcript、error message，先归约事件，再等待 listener。
- `AgentSession`：围绕 Core 处理 post-run action，最后发出 `agent_settled`。

`agent_end` listener 阻塞时，Core 的 `is_streaming` 仍为 true；即使某次 Core 已结束，Session 也可能因为 retry 或 compaction 继续保持 active。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s07_control_boundaries/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s07_control_boundaries.py
```

示例先产生 error，再执行 retry，最后才 settled。整个过程不访问网络。

## 关键测试

- 正常 stop 的顺序是 `agent_end -> agent_settled`。
- retry 位于两次 `agent_end` 之间，不能在第一次 `agent_end` 时宣布 settled。
- compaction 位于 `agent_end` 和 settled 之间。
- 异步 `agent_end` listener 完成前 Core 不 idle。
- abort 生成 aborted assistant，并完成最终清理。
- Provider 抛错被转换成 error assistant。
- 活跃 Session 不能接受第二个 prompt。
- Core 的最后一个 loop 事件是 `agent_end`，Session 的最终稳定事件是 `agent_settled`。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| `RunPlan` 直接描述响应和后处理 | Pi 根据 AssistantMessage、retry 设置、压缩状态和队列动态决定 |
| `AgentCore` 用脚本响应 | Pi Core 调用完整 Provider/工具 loop |
| `AgentSession` 只模拟 retry/compaction/continuation | Pi 还持久化事件、运行扩展 handler 和管理更多恢复状态 |
| `AbortSignal` 只有布尔状态 | Pi 使用标准 `AbortController`，Provider 和工具各自负责响应 signal |

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent.ts)：`runWithLifecycle`、`handleRunFailure`、`finishRun`、`processEvents`。
- [`agent-session.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/agent-session.ts)：`_runAgentPrompt`、`_handlePostAgentRun`、`_emitAgentSettled`。
- [`extensions/types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/extensions/types.ts)：`AgentSettledEvent` 的定义和“没有自动后处理后才 settled”的说明。
- [`agent.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent.test.ts)：异步 listener、abort、并发 prompt 和 idle 测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

系统 2 完成后进入第 08 章：上下文边界，研究 `AgentMessage[]` 如何经过 transform 和 convert 变成 Provider 可接受的消息。
