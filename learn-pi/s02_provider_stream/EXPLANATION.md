# `code.py` 结构化解读：Provider 流与 EventStream

> 代码文件：[`code.py`](./code.py)
>
> 本章重点：模型不再一次性返回完整回答，而是通过事件流逐步返回；程序实时消费这些事件，并在最后得到一条权威的完整 assistant message。

## 1. 先看它解决了什么问题

第 01 章的 Provider 是一次性返回完整消息：

```text
Agent Loop -> Provider.complete()
                 |
                 v
          完整 AssistantMessage
```

真实模型通常是边生成边返回内容。第 02 章把流程改成：

```text
Agent Loop -> Provider.stream()
                 |
                 +-- start
                 +-- text_start
                 +-- text_delta
                 +-- text_delta
                 +-- text_end
                 +-- done
```

这样可以做到两件事：

1. 模型还没有生成完时，界面就能实时显示内容。
2. 调用方最终仍然可以等待一条完整、确定的 assistant message。

本章代码的核心不是“按字符打印文本”，而是设计一个同时支持**增量事件消费**和**最终结果等待**的异步流。

## 2. 整体心智模型

把代码分成三层：

```text
生产者：scripted_text_stream()
    负责产生 start、delta、done 等事件

中间层：EventStream
    负责排队事件、识别终止、保存最终结果

消费者：assemble_assistant_response()
    负责组装 partial，并更新上下文
```

完整过程是：

```text
创建 stream
    |
    v
启动异步生产任务
    |
    v
生产者 push 事件到队列
    |
    v
消费者 async for 读取事件
    |
    +-- 中间事件：更新 partial
    |
    +-- done/error：读取最终结果
                         |
                         v
                 替换上下文中的 partial
                         |
                         v
                    返回最终消息
```

## 3. `EventStream[T, R]` 是什么

```python
class EventStream(Generic[T, R]):
```

这里：

- `T` 表示流中每个事件的类型。
- `R` 表示整个流最终产生的结果类型。

在本章的具体实现中：

```python
T = AssistantStreamEvent
R = AssistantMessage
```

因此，流中会不断产生 `AssistantStreamEvent`，最终结果是一条 `AssistantMessage`。

### 3.1 两条独立通道

`EventStream` 同时提供两种读取方式：

```python
async for event in stream:
    ...
```

用于按顺序读取所有事件，包括中间更新。

```python
final = await stream.result()
```

用于等待最终结果，不需要消费事件迭代器。

可以画成：

```text
                 start -> delta -> delta -> done
                /                              \
事件消费通道： async for                         \
                                                \
最终结果通道： await result() -> final message
```

这两条通道不是二选一。一个消费者可以实时监听事件，另一个调用方也可以直接等待最终结果。

### 3.2 内部状态

```python
self._queue = asyncio.Queue()
self._done = False
self._result_value = _MISSING
self._result_future = None
```

各字段的作用：

| 字段 | 作用 |
|---|---|
| `_queue` | 保存还没有被消费者读取的事件 |
| `_done` | 标记流是否已经结束 |
| `_result_value` | 已经确定的最终结果 |
| `_result_future` | 当调用方提前等待 `result()` 时，用于稍后唤醒它 |

消费者还没有启动时，已经 `push()` 的事件仍会留在队列中，不会丢失。

### 3.3 `push()` 的行为

```python
stream.push(event)
```

如果事件不是终止事件，`push()` 只把它放入队列。

如果事件满足完成条件，`push()` 会：

1. 把 `_done` 设为 `True`。
2. 用 `extract_result` 提取最终结果。
3. 保存或解析等待中的 `result()`。
4. 把终止事件放入队列。
5. 再放入 `_SENTINEL` 结束标记。

特别要注意：

> 终止事件本身也会交给 `async for`，消费者不会看不到 `done` 或 `error`。

完成之后再次调用 `push()` 会被忽略：

```python
if self._done:
    return
```

### 3.4 `async for` 如何结束

`EventStream` 实现了：

```python
def __aiter__(self):
    return self

async def __anext__(self):
    item = await self._queue.get()
    if item is _SENTINEL:
        raise StopAsyncIteration
    return item
```

因此：

- 队列有事件时，返回事件。
- 队列暂时为空时，当前协程等待。
- 取到 `_SENTINEL` 时，抛出 `StopAsyncIteration`，`async for` 结束。

这里的 `await self._queue.get()` 是异步等待当前事件，不是开启新线程。

### 3.5 `end()` 的行为

```python
stream.end(result)
```

`end()` 用于手动结束流，适用于没有 `done` / `error` 事件、但调用方明确提供了最终结果的情况。

例如：

```python
stream.push("progress")
stream.end("manual result")
```

事件迭代器会收到 `progress`，`result()` 会得到 `manual result`。

## 4. Assistant 消息和事件类型

### 4.1 消息 block

```python
class TextBlock:
    text: str

class ThinkingBlock:
    text: str

class ToolCallBlock:
    id: str
    name: str
    arguments_json: str
```

`AssistantMessage.content` 可以包含：

- 文本 block。
- 思考 block。
- 工具调用 block。

```python
AssistantBlock = TextBlock | ThinkingBlock | ToolCallBlock
```

本章虽然定义了思考和工具调用类型，但 demo 只生成文本事件。工具参数的增量拼接和执行会在后续章节展开。

### 4.2 `AssistantStreamEvent`

```python
@dataclass(frozen=True, slots=True)
class AssistantStreamEvent:
    type: EventType
    partial: AssistantMessage | None = None
    content_index: int | None = None
    delta: str | None = None
    content: str | None = None
    message: AssistantMessage | None = None
    reason: StopReason | None = None
```

关键字段：

| 字段 | 含义 |
|---|---|
| `type` | 当前事件种类 |
| `partial` | 截至当前时刻的完整 assistant 快照 |
| `delta` | 当前这次新增的片段 |
| `content` | 一个内容块最终的完整内容 |
| `message` | 终止事件携带的最终消息 |
| `content_index` | 当前事件对应哪个内容块 |
| `reason` | 停止原因 |

### 4.3 `delta` 和 `partial` 的区别

假设模型要生成：

```text
流式回答
```

事件可能是：

```text
事件                         delta       partial
start                                    ""
text_delta                "流"          "流"
text_delta                "式"          "流式"
text_delta                "回"          "流式回"
text_delta                "答"          "流式回答"
done                                      "流式回答"
```

- `delta` 只表示本次增加了什么。
- `partial` 表示截至当前已经生成的全部内容。

本实现直接使用 `partial` 更新上下文，不需要消费者自己把所有 `delta` 拼接起来。

## 5. 哪些事件会结束响应

```python
class AssistantMessageEventStream(EventStream[...]):
    def __init__(self):
        super().__init__(
            is_complete=lambda event: event.type in {"done", "error"},
            ...
        )
```

本章规定：

```text
start、text_start、text_delta、text_end
    中间事件，不结束响应

done
    正常结束

error
    错误或中止，结束响应
```

收到 `done` 或 `error` 后，流会被标记为完成，后续事件会被忽略。

`extract_result` 的逻辑是：

```python
event.message
```

如果终止事件没有携带 `message`，代码会构造一条错误的 `AssistantMessage`，避免 `result()` 没有结果可返回。

## 6. `assemble_assistant_response()`：组装 partial

这是本章最重要的函数，它对应 Pi 生产代码中的 `streamAssistantResponse()`：

```python
async def assemble_assistant_response(
    stream,
    context_messages=None,
) -> AssembledResponse:
```

### 6.1 收到 `start`

```python
if event.type == "start":
    partial = event.partial or AssistantMessage(())
    messages.append(partial)
```

开始时建立一条临时的 assistant 消息，并把它放入上下文。

如果传入了 `context_messages`，这个列表会被原地修改，模拟 Agent 的 transcript 被实时更新。

### 6.2 收到中间更新

```python
elif event.type in _UPDATE_EVENTS:
    partial = event.partial or partial
    messages[-1] = partial
```

每次收到 `text_delta`、`thinking_delta` 或 `toolcall_delta`，就用最新的 partial 替换上下文中的最后一条消息。

必须替换，不能追加。否则上下文会变成：

```text
""
"流"
"流式"
"流式回"
"流式回答"
```

正确结果应该始终只有一条正在生成的 assistant 消息：

```text
"流式回答"
```

如果更新事件在 `start` 之前到达：

```python
if partial is None:
    trace.append(AssemblyTrace("ignored_update", event.type))
    continue
```

代码会忽略它，因为没有可供替换的 partial。

### 6.3 收到 `done` 或 `error`

```python
elif event.type in {"done", "error"}:
    final = await stream.result()
```

终止事件到达后，组装器取得最终消息：

- 已经有 partial：用 `final` 替换最后一条 partial。
- 没有 `start`：直接把 `final` 加入上下文，并补发一个 `message_start` 记录。
- 记录 `message_end`。
- 返回 `AssembledResponse`。

核心原则是：

> partial 用于实时展示，`done.message` 或 `error.message` 才是最终权威结果。

即使最后一次 delta 看起来已经完整，也不能根据 delta 猜测最终状态。最终消息还可能携带 `stop_reason`、错误信息和其他元数据。

## 7. `scripted_text_stream()`：模拟 Provider

```python
def scripted_text_stream(
    text: str,
    *,
    delay: float = 0.0,
) -> AssistantMessageEventStream:
```

它不访问真实模型，只是创建一个事件流，然后按顺序产生预设事件。

内部定义了生产协程：

```python
async def produce():
    ...
```

并用：

```python
asyncio.create_task(produce())
```

让它异步运行，再立刻把 stream 返回给消费者。

`create_task()` 创建的是 asyncio 任务，不是新的操作系统线程。

生产流程如下：

```python
stream.push(AssistantStreamEvent("start", ...))
stream.push(AssistantStreamEvent("text_start", ...))

for character in text:
    built += character
    partial = AssistantMessage((TextBlock(built),))
    stream.push(AssistantStreamEvent("text_delta", partial=partial, ...))
    await asyncio.sleep(delay)  # delay 大于 0 时模拟生成间隔

stream.push(AssistantStreamEvent("text_end", ...))
stream.push(AssistantStreamEvent("done", message=final, ...))
```

## 8. demo 的完整时序

```python
stream = scripted_text_stream("流式回答")
result = await assemble_assistant_response(stream)
```

可以分成两条并发的协作流程：

```text
生产者 produce                     消费者 assemble
       |                                  |
       | 返回 stream                      |
       |                                  | async for 等待
       | push(start) -------------------> |
       | push(text_start) --------------> |
       | push(text_delta) --------------> | 替换 partial
       | push(text_delta) --------------> | 替换 partial
       | push(text_delta) --------------> | 替换 partial
       | push(text_end) ----------------> |
       | push(done) --------------------> | 读取 final，替换 partial
       |                                  | 返回结果
```

demo 打印的 trace 是：

```text
message_start
message_update   text_start
message_update   text_delta
message_update   text_delta
message_update   text_delta
message_update   text_delta
message_update   text_end
message_end      stop
```

最终结果：

```text
Final message: 流式回答
Stream result: 流式回答
```

底层事件有很多种，但组装器把它们转换成了更简单的生命周期记录：

```text
message_start -> message_update -> message_end
```

## 9. 错误和边界情况

### `error` 是终止事件

如果收到：

```python
AssistantStreamEvent(
    "error",
    message=AssistantMessage((), "error", "upstream failed"),
)
```

那么：

1. 流被标记为完成。
2. 最终消息的 `stop_reason` 是 `error`。
3. 之前的 partial 被错误消息替换。
4. 后续 `text_delta` 会被忽略。

### 没有 `start` 但直接 `done`

代码也能处理这种情况：

```text
done(final_message)
```

它会直接把最终消息加入上下文，并记录：

```text
message_start: terminal event without start
message_end
```

### 手动结束

如果代码调用：

```python
stream.end(final)
```

组装器退出 `async for` 后，再通过 `await stream.result()` 取到最终结果。

## 10. 与第 01 章的关系

| 第 01 章 | 第 02 章 |
|---|---|
| Provider 返回完整 `AssistantMessage` | Provider 产生 `AssistantStreamEvent` |
| Agent 直接处理最终消息 | 先组装 partial，再得到最终消息 |
| 一次看到完整回答 | 可以实时看到生成过程 |
| 只有一个返回值 | 事件迭代器和最终结果两条通道 |
| 重点是工具回环 | 重点是 Provider 响应生命周期 |

第 02 章仍然没有执行工具。它只是让 `ToolCallBlock` 和 `toolcall_*` 事件具备表示能力，工具参数拼接、校验和执行属于后续章节。

## 11. 代码中几个容易混淆的概念

### `EventStream` 不是大模型

它只是一个事件传输工具：

```text
Provider 负责产生事件
EventStream 负责传递事件
assemble_assistant_response 负责消费并组装
```

### `partial` 不是最终消息

`partial` 是当前生成进度的快照，可以被后续事件替换。

```text
partial = 当前状态
final   = 最终权威状态
```

### `result()` 不是重新请求模型

```python
await stream.result()
```

只是等待或读取这个 stream 已经产生的最终结果，不会再次调用 Provider。

### `await` 不是新线程

```python
item = await self._queue.get()
```

表示当前协程暂时等待队列里的下一个事件。事件循环可以在这段时间运行生产者或其他协程，但不会因为 `await` 自动创建线程。

## 12. 建议的阅读顺序

重新阅读源码时建议按以下顺序：

1. 先看 `demo()`，确认最终想得到什么。
2. 看 `scripted_text_stream()`，理解事件如何产生。
3. 看 `AssistantStreamEvent`，理解每个事件携带什么数据。
4. 看 `EventStream.push()`、`__anext__()` 和 `result()`，理解事件如何排队和结束。
5. 最后看 `assemble_assistant_response()`，理解 partial 如何被替换成最终消息。

最值得记住的三处逻辑是：

```python
stream.push(event)
```

生产事件。

```python
messages[-1] = partial
```

用最新快照替换旧的 partial。

```python
final = await stream.result()
```

取得终止事件对应的最终消息。

## 总结

第 02 章实现的是一个简化版的流式模型响应系统：

```text
产生事件
  -> 事件进入异步队列
  -> 消费者实时读取
  -> partial 持续替换
  -> done/error 标记结束
  -> final message 替换 partial
```

一句话记忆：

> `async for` 负责看过程，`result()` 负责拿结果，`partial` 负责实时状态，`done.message` 负责最终定稿。

在仓库根目录可以这样验证：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s02_provider_stream/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s02_provider_stream.py
```
