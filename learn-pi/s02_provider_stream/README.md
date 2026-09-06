# 第 02 章：Provider 流与 EventStream

## 本章问题

第 01 章把 Provider 简化成一次返回完整消息。但真实 Agent 需要在模型仍生成时显示文本、思考过程和工具调用参数，因此 Pi 的 Provider 返回的是 `AssistantMessageEventStream`，而不是直接返回最终消息。

本章回答两个问题：

1. 一个异步事件流如何同时支持实时消费和最终结果等待？
2. partial assistant message 如何随着事件更新，最后被权威的 `done` / `error` 消息替换？

## 源码调用链

```text
Provider.streamSimple()
  -> AssistantMessageEventStream.push(start)
  -> push(text/thinking/toolcall updates)
  -> push(done 或 error)

agent-loop.ts::streamAssistantResponse()
  -> for await (event of response)
  -> context.messages 写入/替换 partial
  -> response.result()
  -> message_end(finalMessage)
```

Pi 的 `EventStream` 有两个独立出口：

- `for await`：按顺序消费事件。
- `result()`：等待最终的 assistant message，不需要先消费事件。

满足完成判断的事件仍然会被迭代器收到；完成后再 `push` 的事件会被忽略。

## 事件协议

本章代码使用 `AssistantStreamEvent` 投影 Pi 的事件联合类型：

| 事件 | 含义 |
|---|---|
| `start` | 建立空的或初始 partial message |
| `text_start` / `text_delta` / `text_end` | 文本块的生命周期和增量 |
| `thinking_*` | 思考块的生命周期和增量 |
| `toolcall_*` | 工具调用及其 JSON 参数的增量 |
| `done` | 正常终止，携带最终 assistant message |
| `error` | 错误或 abort，携带错误 assistant message |

真实 Pi 要求更新和终止事件都不能出现在 `start` 之前。`partial` 是响应到目前为止的状态；`done.message` 才是最终权威结果。

## 最小实现

`EventStream[T, R]` 用 `asyncio.Queue` 保存事件，用独立结果值模拟 TypeScript Promise：

```python
stream.push(event)       # 生产事件
async for event in stream:
    ...                  # 实时消费
final = await stream.result()  # 等待最终结果
```

`assemble_assistant_response()` 对应 Pi 的 `streamAssistantResponse()`：

1. `start` 时把 partial 加入 transcript。
2. 中间更新替换 transcript 的最后一条 assistant message。
3. `done` / `error` 到达时读取 `stream.result()`。
4. 用最终消息替换 partial，并发出 `message_end`。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s02_provider_stream/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s02_provider_stream.py
```

示例 Provider 按字符产生 `text_delta`，但事件顺序和终止语义与 Pi 的事件流一致。它没有访问网络。

## 关键测试

测试覆盖：

- 事件在消费者启动前进入队列仍不会丢失。
- 完成事件既解析给消费者，也解析为 `result()`。
- 完成后推入的事件被忽略。
- 手动 `end(result)` 可以结束没有完成事件的流。
- `done.message` 会覆盖之前的 partial，而不是把两条 assistant 消息都留下。
- `error` 是终止事件，不能继续消费后续增量。
- 没有 `start` 但直接 `done` 时，组装器仍建立最终消息。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| `asyncio.Queue` | TypeScript 数组队列和 waiting resolver |
| dataclass 事件 | TypeScript discriminated union |
| 字符串 text delta | 各 Provider 依据 API 转换的增量事件 |
| 只展示一个脚本 Provider | Pi 支持多个 Provider/API 适配器 |
| 组装器只维护 assistant message | Pi 同时向 Agent 事件订阅者发送快照 |

本章仍然不执行工具。工具调用事件的参数拼接、校验和执行属于第 04、05 章。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`event-stream.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/ai/src/utils/event-stream.ts)：`EventStream.push`、`end`、异步迭代器和 `result`。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/ai/src/types.ts)：`AssistantMessageEvent` 和 `Context`。
- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`streamAssistantResponse`。

逐条源码定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 03 章把底层响应流映射为 Agent 的 `agent_start`、`turn_start`、`message_update`、`tool_execution_*` 和 `agent_end` 事件，观察状态如何由事件协议驱动。
