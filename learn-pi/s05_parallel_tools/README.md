# 第 05 章：并行工具与结果顺序

## 本章问题

一个 assistant message 可能同时包含多个 tool call。Pi 默认允许可并行工具执行，但不能让并发完成顺序破坏模型上下文的消息顺序。

本章区分三个顺序：

1. **源码顺序**：assistant content 中 tool call 的顺序。
2. **完成顺序**：工具真正完成并发出 `tool_execution_end` 的顺序。
3. **结果顺序**：生成 `ToolResultMessage` 并写回上下文的顺序。

Pi 的约束是：完成事件按完成顺序，tool result 按源码顺序。

## 源码调用链

```text
executeToolCalls()
  -> 判断 config.toolExecution / tool.executionMode
  -> executeToolCallsSequential()
     或 executeToolCallsParallel()
        -> 按源码顺序 preflight
        -> 并发执行 prepared calls
        -> completion-order tool_execution_end
        -> source-order toolResult messages
```

并行路径不是把所有调用直接扔进任务池：准备阶段仍然按源码顺序进行。缺失工具、校验失败或策略阻止会先得到 immediate outcome，其他合法调用仍可继续执行。

## 最小实现

`execute_tool_calls()` 返回：

```python
ToolBatchResult(
    messages=...,             # 模型看到的源码顺序
    execution_end_order=...,  # 工具完成顺序
    result_message_order=..., # 写回顺序
    events=...,
    terminated=...,
)
```

执行策略：

- `tool_execution="sequential"`：整个 batch 顺序执行。
- 默认 `parallel`：所有工具都允许并行时并发执行。
- 任一工具 `execution_mode="sequential"`：整个 batch 强制顺序执行。

## 截断保护

如果 assistant 的 `stopReason` 是 `length`，Pi 不会因为参数“看起来能解析”就执行工具。所有调用都生成错误 tool result，让模型重新发起完整调用。

这是安全边界，不是普通的参数校验失败；即使只有一个调用被截断，也不能执行该消息里的任何工具。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s05_parallel_tools/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s05_parallel_tools.py
```

示例让慢工具先发起、快工具先完成。你会看到 completion order 与 tool result order 不同。

## 关键测试

- 并行调用确实重叠，完成顺序可以是 `c2, c1`。
- 结果消息仍是 `c1, c2`。
- 全局 sequential 和工具级 sequential 都会禁止重叠。
- 显式 parallel 工具可以并行。
- `length` batch 中没有任何 callable 被执行。
- 一个工具抛错不会取消其他并行工具。
- 只有所有结果都声明 `terminate` 时 batch 才提前终止。
- immediate 缺失工具不会阻止其他合法调用。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| 参数已经假定完成 preflight | Pi 在本章对应位置调用完整 `prepareToolCall` |
| `asyncio.create_task` + `gather` | Promise 工厂 + `Promise.all` |
| 结果是简单字符串 | `AgentToolResult` 还包含 details、usage、图片和动态工具 |
| 只记录核心事件 | Pi 还会发出 tool update，并由 Agent 状态归约 |
| 用 id 字典重建顺序 | Pi 用 `orderedFinalizedCalls` 数组保持源码顺序 |

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`executeToolCalls`、`executeToolCallsSequential`、`executeToolCallsParallel`。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/types.ts)：`ToolExecutionMode`、`AgentTool.executionMode` 和 `AgentToolResult.terminate`。
- [`agent-loop.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent-loop.test.ts)：完成顺序、顺序执行、截断和 terminate 测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 06 章实现 steering 与 follow-up 双队列，观察消息为什么必须在不同的循环边界注入。
