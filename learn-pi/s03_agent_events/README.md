# 第 03 章：Agent 状态与事件协议

## 本章问题

第 02 章解决了 Provider 如何产生增量事件。本章继续向上看：谁来消费这些事件，谁拥有会话 transcript，UI 如何知道当前正在生成什么，工具是否仍在执行？

Pi 用 `Agent` 包住低层 `agent-loop`。它不是另一个模型循环，而是一个**事件归约器 + 生命周期控制器**。

## 源码调用链

```text
Agent.prompt()
  -> runWithLifecycle()
     -> runAgentLoop(..., event => processEvents(event))
        -> processEvents()
           -> reduce AgentState
           -> await every subscriber
  -> finishRun()
```

`Agent` 的关键职责：

- `prompt()` 防止同一个 Agent 同时运行两个 prompt。
- `runWithLifecycle()` 创建一次运行专用的 abort signal，并清理运行态。
- `processEvents()` 先更新状态，再按注册顺序等待监听器。
- `finishRun()` 在 `agent_end` 监听器全部完成后，才清除 streaming 状态。

## 状态字段

| 状态 | 由什么事件驱动 | 语义 |
|---|---|---|
| `is_streaming` | 运行开始/结束 | Agent 是否仍拥有活跃运行 |
| `streaming_message` | `message_start/update`、`message_end` | 当前尚未结束的消息 |
| `messages` | `message_end` | 已完成并进入 transcript 的消息 |
| `pending_tool_calls` | `tool_execution_start/end` | 正在执行的工具调用 id 集合 |
| `error_message` | 带错误 assistant 的 `turn_end` | 最近一次失败信息 |

注意：`agent_end` 不是 idle 的同义词。Pi 会先发出 `agent_end`，再等待订阅者；只有监听器完成后，`isStreaming` 才变成 `false`。

## 最小实现

本章的 `Agent` 接收一个脚本化低层 Runner。Runner 只负责发事件，Agent 不关心事件来自真实 Provider 还是测试桩：

```python
await emit(AgentEvent("message_start", message=partial))
await emit(AgentEvent("message_update", message=updated))
await emit(AgentEvent("message_end", message=final))
```

`_process_event()` 对每个事件执行两步：

1. 归约内部状态。
2. 顺序执行订阅者，并等待异步订阅者。

因此订阅者在收到 `tool_execution_start` 时已经能读到 `pending_tool_calls`，在收到 `message_end` 时已经能读到更新后的 transcript。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s03_agent_events/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s03_agent_events.py
```

示例包含一个工具调用生命周期，但工具本身不在本章执行；这里只观察 `pending_tool_calls` 如何被加入和清除。

## 关键测试

- 完整事件序列最终形成 user、assistant、toolResult、assistant transcript。
- 监听器按注册顺序运行，且看到的是已经归约后的状态。
- `agent_end` 监听器未释放时，`prompt()` 和 `wait_for_idle()` 都不会完成。
- 取消订阅后不再收到事件。
- Runner 抛错时，Agent 补发错误 assistant 的完整结束生命周期。
- 运行中再次调用 `prompt()` 会被拒绝。
- 所有监听器收到同一个本次运行的 abort signal。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| Runner 直接发送 `AgentEvent` | Pi 由 `agent-loop` 将 Provider 流和工具执行转换为事件 |
| 消息使用简单 dataclass | Pi 使用 LLM Message 和可扩展 AgentMessage 联合类型 |
| `AbortSignal` 只有 `aborted` 字段 | Pi 使用标准 `AbortController` / `AbortSignal` |
| 工具事件由脚本生成 | Pi 的工具状态由真实执行流水线生成 |
| 没有 steering/follow-up 队列 | Pi 的 Agent 还拥有两套 PendingMessageQueue |

双队列和工具执行细节分别在第 05、06 章展开，本章只固定状态归约边界。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent.ts)：`Agent.subscribe`、`prompt`、`runWithLifecycle`、`handleRunFailure`、`finishRun`、`processEvents`。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/types.ts)：`AgentState` 和 `AgentEvent`。
- [`agent.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent.test.ts)：错误生命周期、异步订阅者、`waitForIdle` 和并发 prompt 测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 04 章进入工具契约：工具如何按名称查找，参数如何校验，准备阶段如何阻止一次调用，以及错误如何作为 `ToolResultMessage` 回到模型。
