# 第 04 章：工具契约与参数校验

## 本章问题

模型发出的 tool call 还不是一次安全的工具执行。Pi 会先查找工具、准备参数、校验参数，再询问 `beforeToolCall`；只有这些步骤都通过，才会调用工具函数。

```text
tool call
  -> lookup
  -> prepareArguments
  -> validateToolArguments
  -> beforeToolCall
  -> execute
  -> ToolResultMessage
```

## 源码调用链

```text
runLoop()
  -> executeToolCalls()
     -> prepareToolCall()
        -> prepareToolCallArguments()
        -> validateToolArguments()
        -> beforeToolCall()
     -> executePreparedToolCall()
        -> tool.execute()
     -> createToolResultMessage()
```

`prepareToolCall()` 返回两种结果：

- prepared：拥有已经校验的参数，可以执行。
- immediate：不执行工具，直接生成错误结果，例如工具不存在、参数错误、策略阻止或 abort。

## 参数边界

代码使用一个小型 JSON Schema 子集代替 Pi 的 TypeBox：object、array、string、number、integer、boolean，以及 required/properties。验证前会复制参数，避免校验器或后续逻辑改变模型原始参数。

一个重要的 Pi 语义是：

> `beforeToolCall` 收到的是已校验参数；如果 hook 修改参数，Agent 不会再次校验，而是把修改后的对象传给 `execute`。

这不是推荐的业务习惯，而是上游当前契约。本章测试特意固定这个行为。

## 最小实现

`execute_tool_call()` 将所有失败变成 `ToolOutcome`：

```python
outcome = await execute_tool_call(tools, call)
if outcome.result.is_error:
    # 作为 tool result 回到下一次模型请求
    ...
```

工具异常不会直接击穿 Agent Loop。缺失工具、校验失败、阻止执行和工具抛错都带着原始 `tool_call_id` 与名称返回，便于模型修正调用。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s04_tool_contract/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s04_tool_contract.py
```

示例中的 `edit` 工具把 shorthand 参数转换为 `edits` 数组，再执行；随后用策略 hook 阻止同一个调用。

## 关键测试

- 找不到工具时不执行 callable。
- 无效参数在执行前被拒绝。
- `prepare_arguments` 可以将模型 shorthand 转成 schema 允许的形状。
- 校验参数是副本，原始模型参数不被修改。
- `beforeToolCall` 可以阻止执行并设置 `terminate`。
- hook 修改已校验参数后，执行阶段使用修改值且不重新校验。
- 工具异常被转成错误 `ToolResultMessage`。
- abort 状态阻止真正执行。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| 内置小型 JSON Schema 校验器 | TypeBox schema + Value.Convert + 格式化错误 |
| 工具返回字符串 | `AgentToolResult` 支持文本/图片、details、usage 和新增工具 |
| 同步/异步 callable | `AgentTool.execute` 是带 signal 和 update callback 的异步函数 |
| 没有 after hook | Pi 还有 `afterToolCall`，可覆盖结果字段 |
| 单个调用流水线 | Pi 还要决定顺序/并行执行并维护事件顺序 |

并发执行、tool execution update 和工具结果持久化顺序留到第 05 章。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`prepareToolCallArguments`、`prepareToolCall`、`executePreparedToolCall`。
- [`validation.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/ai/src/utils/validation.ts)：`validateToolArguments`。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/types.ts)：`AgentTool`、`BeforeToolCallResult` 和 `AgentToolResult`。
- [`agent-loop.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent-loop.test.ts)：参数准备、hook 修改参数、阻止和工具结果测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 05 章进入多个 tool call：默认并行执行如何与工具级顺序约束、完成事件顺序和 transcript 源码顺序同时成立。
