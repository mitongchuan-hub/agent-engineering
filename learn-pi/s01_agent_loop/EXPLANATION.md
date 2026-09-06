# `code.py` 结构化解读：最小 Agent Loop

> 目标：理解这份代码如何把“用户问题、模型回答、工具调用、工具结果”组织成一个可重复的 Agent 闭环。
>
> 代码文件：[`code.py`](./code.py)

## 1. 先记住一句话

这不是一个“只调用一次大模型”的程序，而是一个负责调度的循环：

```text
用户问题
   |
   v
请求模型
   |
   v
assistant 回答
   |
   +-- 没有工具调用 --> 结束，返回最终回答
   |
   +-- 有工具调用 --> 执行工具
                         |
                         v
                    生成 tool result
                         |
                         v
                 把结果放回上下文
                         |
                         v
                    再请求模型
```

最小闭环可以写成伪代码：

```python
messages = 历史消息 + 用户问题

while True:
    assistant = await provider.complete(messages)
    messages.append(assistant)

    if assistant 是 error 或 aborted:
        break

    results = 执行 assistant 里的所有 tool call
    messages.extend(results)

    if assistant 没有 tool call:
        break
```

其中，Agent 自己并不“理解”文件内容或决定答案。它负责：

1. 维护消息上下文。
2. 把上下文交给模型。
3. 识别模型要求执行的工具。
4. 执行工具并把结果反馈给模型。
5. 判断什么时候结束。

## 2. 一次完整运行长什么样

`demo()` 构造了一个很小的离线场景：

- 内存里有一个虚拟文件 `hello.py`。
- 用户问：`What does hello.py do?`
- 第一次模型响应要求调用 `read_file`。
- 程序执行 `read_file`，得到 `print("hello from Pi")`。
- 第二次模型响应根据工具结果回答：`The file prints "hello from Pi".`

对应的消息序列是：

```text
1. user        What does hello.py do?
2. assistant   tool call: read_file({"path": "hello.py"})
3. toolResult  read_file [ok]: print("hello from Pi")
4. assistant   The file prints "hello from Pi".
```

注意：第 3 条消息不是给用户看的最终答案，它是给下一次模型请求看的输入。模型正是通过它知道 `hello.py` 的内容。

## 3. 代码的分层结构

可以把 `code.py` 分成五层：

```text
消息模型       TextBlock / ToolCall / UserMessage / AssistantMessage / ToolResultMessage
工具模型       Tool / ToolExecutor / _execute_tool()
上下文与请求   AgentContext / ModelRequest
模型边界       Provider / ScriptedProvider
循环与演示     run_agent_loop() / _message_summary() / demo()
```

依赖关系大致是：

```text
AgentContext ─────┐
                   v
prompts ------> run_agent_loop() <------ Provider
                   |
                   v
                 Tool
                   |
                   v
             ToolResultMessage
                   |
                   └──── 追加回上下文，再次交给 Provider
```

## 4. 消息模型：模型和工具如何“对话”

### 4.1 `TextBlock` 和 `ToolCall`

```python
@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str

@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]
```

`AssistantMessage.content` 不是简单字符串，而是由多个 block 组成：

- `TextBlock`：模型生成的普通文本。
- `ToolCall`：模型要求程序调用某个工具。

因此一条 assistant 消息可以是：

```python
AssistantMessage(
    content=(
        TextBlock("我先读取文件。"),
        ToolCall("call-1", "read_file", {"path": "hello.py"}),
    ),
    stop_reason="toolUse",
)
```

本章的 demo 只放了一个 `ToolCall`，但数据结构允许一条消息包含多个调用。

`ToolCall.id` 很重要：工具结果通过这个 id 与原始调用对应起来，避免多个工具调用之间发生混淆。

### 4.2 三种顶层消息

#### `UserMessage`

```python
UserMessage(content="What does hello.py do?")
```

表示用户输入，固定带有 `role="user"`。

#### `AssistantMessage`

```python
AssistantMessage(
    content=(ToolCall(...),),
    stop_reason="toolUse",
)
```

表示模型输出，包含：

- `content`：文本 block 和工具调用 block 的元组。
- `stop_reason`：模型为什么停止生成。
- `error_message`：模型请求失败时的可选错误信息。
- `tool_calls`：一个属性，自动从 `content` 中筛选出所有 `ToolCall`。

`tool_calls` 的实现是：

```python
return tuple(block for block in self.content if isinstance(block, ToolCall))
```

也就是说，循环不需要自己遍历文本和调用并判断类型，只需读取 `assistant.tool_calls`。

#### `ToolResultMessage`

```python
ToolResultMessage(
    tool_call_id="call-1",
    tool_name="read_file",
    content='print("hello from Pi")',
    is_error=False,
)
```

表示程序执行工具后的结果。它会被追加到上下文，作为下一次模型请求的一部分。

如果工具失败，`is_error=True`，但消息仍然会返回给模型，让模型有机会解释错误、换一个方案或请求用户补充信息。

### 4.3 `Message` 是统一消息类型

```python
Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage
```

`Message` 是一个类型别名，表示消息列表中允许出现上述三类消息。这样 `AgentContext.messages` 和 `ModelRequest.messages` 可以使用同一套协议。

注释“Provider 只看统一的 Message”表达的是一个边界：Provider 不需要知道工具函数内部如何执行，只接收标准化后的消息。

## 5. 工具模型：工具不是模型自己执行的

### 5.1 `Tool` 的组成

```python
@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    execute: ToolExecutor
```

一个工具有三部分：

| 字段 | 含义 |
|---|---|
| `name` | 模型请求时使用的工具名 |
| `description` | 工具用途说明；本章的简化 Provider 没有实际使用它 |
| `execute` | 真正执行工具的 Python 函数 |

工具函数的接口是：

```python
ToolExecutor = Callable[[str, Mapping[str, Any]], str | Awaitable[str]]
```

它接收：

- 工具调用 id。
- 模型传来的参数字典。

它可以：

- 直接返回字符串。
- 返回一个异步结果，循环会等待它完成。

### 5.2 `_execute_tool()` 的作用

`_execute_tool()` 是工具执行边界。它做两件事：

1. 兼容同步工具和异步工具。
2. 把工具抛出的异常转换成 `ToolResultMessage`。

关键逻辑可以理解为：

```python
try:
    value = tool.execute(call.id, call.arguments)
    if value 是 awaitable:
        value = await value
    return 成功的 ToolResultMessage
except Exception as error:
    return 失败的 ToolResultMessage("Tool error: ...")
```

为什么不直接把异常抛出？因为工具失败属于模型可以处理的运行结果，不一定代表整个 Agent 运行失败。例如模型可以看到 `permission denied` 后告诉用户权限不足，或者改用另一个工具。

## 6. 上下文、请求和 Provider

### 6.1 `AgentContext`：一次 Agent 调用的配置和历史

```python
@dataclass(slots=True)
class AgentContext:
    system_prompt: str
    messages: list[Message]
    tools: list[Tool]
```

它保存：

- `system_prompt`：系统指令。
- `messages`：本次调用之前已有的 transcript，也就是历史消息。
- `tools`：当前可用工具目录。

### 6.2 `ModelRequest`：发送给模型的快照

```python
@dataclass(frozen=True, slots=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[Message, ...]
    tool_names: tuple[str, ...]
```

每一轮循环都会新建一个 `ModelRequest`。这里把消息和工具名转换成 `tuple`，表示这是发给 Provider 的只读快照，不应在请求发出后继续修改。

本章是教学简化版，所以请求里只有工具名，没有工具参数 schema 和完整 description。真实模型通常需要 schema 才能可靠地产生合法参数。

### 6.3 `Provider`：模型服务的抽象边界

```python
class Provider(Protocol):
    async def complete(self, request: ModelRequest) -> AssistantMessage:
        """返回一条完整的 assistant 消息。"""
```

`Provider` 只规定接口，不关心具体实现是：

- 云端大模型 API。
- 本地模型。
- 测试桩。

这使用了 Python 的 `Protocol`：只要一个对象提供同名、同签名的 `complete()` 方法，就可以作为 Provider 使用。

### 6.4 `ScriptedProvider`：确定性的测试替身

`ScriptedProvider` 不访问真实模型，而是按顺序返回预先写好的响应：

```python
responses = [
    AssistantMessage((ToolCall(...),), stop_reason="toolUse"),
    AssistantMessage((TextBlock("最终回答"),)),
]
```

每次 `complete()`：

1. 把收到的 `ModelRequest` 保存到 `requests`。
2. 取出下一条预设响应。
3. 如果响应已经用完，抛出 `RuntimeError`。

它的价值是让我们可以精确观察：第二次请求是否真的带上了 `toolResult`，而不受网络、模型随机性或 API key 影响。

## 7. `run_agent_loop()` 逐步拆解

这是整份代码的核心函数。

### 7.1 函数输入和输出

```python
async def run_agent_loop(
    prompts: Sequence[UserMessage],
    context: AgentContext,
    provider: Provider,
) -> AgentLoopResult:
```

输入：

- `prompts`：本次新收到的用户消息。
- `context`：系统提示、历史 transcript、工具目录。
- `provider`：模型调用实现。

输出：

```python
@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    new_messages: tuple[Message, ...]
    final_messages: tuple[Message, ...]
    trace: tuple[TraceEntry, ...]
```

三个结果的区别：

| 返回值 | 内容 | 用途 |
|---|---|---|
| `new_messages` | 本次调用新增的消息 | 持久化本轮增量 |
| `final_messages` | 历史消息加上本次新增消息 | 查看完整 transcript，或作为后续上下文 |
| `trace` | Agent 生命周期和工具执行事件 | 调试、观测和测试 |

### 7.2 初始化两份消息列表

```python
new_messages = list(prompts)
current_messages = [*context.messages, *prompts]
```

这是本函数最容易混淆、也最值得理解的地方。

假设：

```text
context.messages = [历史消息 H]
prompts         = [新问题 U]
```

初始化后：

```text
new_messages     = [U]
current_messages = [H, U]
```

含义是：

- `current_messages` 是每次真正发给模型的完整上下文。
- `new_messages` 只记录这一次调用新产生的内容。
- `context.messages` 没有被原地追加，所以输入上下文不会被修改。

### 7.3 记录开始事件

函数先创建：

```text
agent_start
turn_start: provider turn 1
message_start: user
message_end: user: ...
```

这些事件不参与模型推理，主要用于观察运行过程。教学实现用 `TraceEntry(event, detail)` 保存事件，而生产系统通常会把事件实时发给订阅者。

### 7.4 每轮只请求一次 Provider

循环每次构造一个请求：

```python
request = ModelRequest(
    system_prompt=context.system_prompt,
    messages=tuple(current_messages),
    tool_names=tuple(tool.name for tool in context.tools),
)
assistant = await provider.complete(request)
```

这里有三个重点：

1. 系统提示每轮都传给模型。
2. 当前完整消息列表每轮都传给模型。
3. 可用工具名从 `context.tools` 中生成。

Provider 返回后，assistant 消息立即加入两份列表：

```python
current_messages.append(assistant)
new_messages.append(assistant)
```

这样后续工具结果和下一轮请求才能建立在这条 assistant 消息之上。

### 7.5 先处理 `error` 和 `aborted`

```python
if assistant.stop_reason in {"error", "aborted"}:
    break
```

这一步在工具执行之前。

即使一个错误响应的 `content` 里看起来有 `ToolCall`，也不能执行它。因为：

- `error` 表示模型请求失败。
- `aborted` 表示请求被中止。
- 这时的工具调用可能是不完整或不可信的。

因此代码记录 `turn_end` 后直接结束本次 Agent 调用。

### 7.6 收集并执行所有工具调用

```python
tool_results = []
for call in assistant.tool_calls:
    ...
```

一条 assistant 消息可能有多个工具调用，代码会逐个处理。对每个调用，流程是：

```text
tool_execution_start
        |
        v
判断 stop_reason 是否为 length
        |
        +-- 是：生成“未执行”的错误结果
        |
        +-- 否：按名字查找工具
                    |
                    +-- 找不到：生成错误结果
                    |
                    +-- 找到：执行工具，异常也转成错误结果
        |
        v
tool_execution_end
message_start/toolResult
message_end/toolResult
        |
        v
追加到 current_messages 和 new_messages
```

#### 工具名查找

```python
tool = next(
    (candidate for candidate in context.tools if candidate.name == call.name),
    None,
)
```

模型只能通过名字请求工具。找不到时，代码不会崩溃，而是返回：

```text
Tool "xxx" not found
```

并设置 `is_error=True`。

#### 工具异常

真正执行由 `_execute_tool(tool, call)` 完成。函数异常会变成类似下面的模型可见消息：

```text
Tool error: permission denied
```

#### `length` 截断

当 `assistant.stop_reason == "length"` 时，代码永远不会执行工具，而是返回：

```text
Tool call "write" was not executed: the response hit the output token limit,
so its arguments may be truncated.
```

原因是模型输出达到 token 上限时，工具名或参数即使“看起来完整”，也不能假定它完整可靠。这个分支是一个重要的执行安全边界。

### 7.7 决定是否进入下一轮

当前轮的所有工具结果追加完成后，代码记录：

```text
turn_end: N tool result(s)
```

然后判断：

```python
if not assistant.tool_calls:
    break
```

- 没有工具调用：说明这条 assistant 消息已经是普通回答，循环结束。
- 有工具调用：工具结果已经放进 `current_messages`，增加轮次，继续请求 Provider。

所以 `stop_reason="toolUse"` 不是唯一的继续条件；实际继续条件是 `assistant.tool_calls` 非空，并且它没有提前被 `error` / `aborted` 分支终止。

### 7.8 返回结果

循环结束时追加：

```text
agent_end: N new message(s)
```

并把三个列表转换成元组返回。调用方可以同时获得：

- 本轮增量。
- 含历史的完整 transcript。
- 调试轨迹。

## 8. 用 demo 追踪真实状态变化

假设初始值是：

```text
context.messages = []
prompts         = [U]
```

状态变化如下：

| 时刻 | `current_messages` | `new_messages` | Provider 请求次数 |
|---|---|---|---:|
| 初始化 | `[U]` | `[U]` | 0 |
| 第一次返回 tool call | `[U, A1]` | `[U, A1]` | 1 |
| 工具执行完成 | `[U, A1, R1]` | `[U, A1, R1]` | 1 |
| 第二次返回最终文本 | `[U, A1, R1, A2]` | `[U, A1, R1, A2]` | 2 |
| 结束 | `[U, A1, R1, A2]` | `[U, A1, R1, A2]` | 2 |
```

其中：

- `U`：`UserMessage`。
- `A1`：带 `ToolCall` 的 `AssistantMessage`。
- `R1`：`ToolResultMessage`。
- `A2`：带最终文本的 `AssistantMessage`。

第二次 Provider 请求的最后一条消息是 `R1`。这就是“工具结果反馈给模型”的关键证据。

如果 `context.messages` 原来有历史消息 `H`，状态则是：

```text
current_messages = [H, U, A1, R1, A2]
new_messages     = [U, A1, R1, A2]
context.messages 仍然是 [H]
```

## 9. `trace` 记录了什么

`TraceEntry` 只有两个字段：

```python
@dataclass(frozen=True, slots=True)
class TraceEntry:
    event: str
    detail: str
```

demo 中一次正常运行的事件顺序是：

```text
agent_start
turn_start
message_start(user)
message_end(user)
message_start(assistant)
message_end(assistant: toolUse)
tool_execution_start
 tool_execution_end
message_start(toolResult)
message_end(toolResult)
turn_end
turn_start
message_start(assistant)
message_end(assistant: stop)
turn_end
agent_end
```

这里的 `trace` 是“发生了什么”的记录，不是“模型上下文”的替代品：

- `final_messages` 用于恢复模型对话内容。
- `trace` 用于观察生命周期和调试。

## 10. 终止和错误行为

| 情况 | 工具是否执行 | 是否继续请求模型 | 原因 |
|---|---:|---:|---|
| 普通文本回答，没有 `ToolCall` | 否 | 否 | 已得到最终回答 |
| `stop_reason="toolUse"`，有调用 | 是 | 是 | 需要把工具结果交给模型 |
| `stop_reason="error"` | 否 | 否 | 模型请求失败，不信任调用内容 |
| `stop_reason="aborted"` | 否 | 否 | 请求已被中止 |
| `stop_reason="length"`，有调用 | 否 | 是 | 返回截断错误，让模型重新处理 |
| 工具名字不存在 | 否 | 是 | 返回 `is_error=True` 的工具结果 |
| 工具函数抛异常 | 工具已开始执行 | 是 | 把异常转换为模型可见错误 |

这里有一个容易忽略的点：工具错误并不等于 Agent 错误。错误结果仍然会加入消息列表，因此 Provider 还有机会返回下一条 assistant 消息。

## 11. Python 语法重点

### `@dataclass`

`@dataclass` 自动生成构造函数等样板代码。例如：

```python
UserMessage("你好")
```

就能创建带 `content` 和固定 `role` 的对象。

### `frozen=True` 与 `slots=True`

- `frozen=True`：创建后不能修改字段，适合表示消息这种值对象。
- `slots=True`：限制对象可拥有的属性，减少意外添加字段，也更节省内存。

`AgentContext` 没有 `frozen=True`，因为它包含运行配置中的可变列表；但 `run_agent_loop()` 仍然不会修改 `context.messages`。

### `Literal`

```python
StopReason = Literal["stop", "toolUse", "length", "error", "aborted"]
```

它用于类型标注，表达 `stop_reason` 只允许这些固定字符串。

### `async`、`await` 和 `asyncio.run`

- `async def` 定义异步函数。
- `await` 等待异步 Provider 或异步工具完成。
- `asyncio.run(demo())` 启动事件循环并执行异步 demo。

这样网络请求、文件操作等未来可能耗时的工作就可以不阻塞整个调度器。

### `cast`

`cast(...)` 只是在类型检查层面告诉工具“这里可以按某个类型理解”。它不会在运行时做真正的类型转换。代码中的 `cast(str, value)` 不会把非字符串值转换成字符串。

## 12. 这份实现刻意没有做什么

它是教学模型，不是完整生产 Agent。与 Pi 的生产实现相比，主要简化包括：

| 本代码 | 生产 Agent 常见实现 |
|---|---|
| Provider 一次返回完整 `AssistantMessage` | Provider 返回增量事件流，逐步形成 assistant 消息 |
| 工具逐个顺序执行 | 可以并行执行，也可以按工具或配置要求串行 |
| 只有 prompt 入口 | 还要处理 continuation、steering、follow-up 等队列 |
| 工具参数只有 `Mapping[str, Any]` | 通常带有可校验的参数 schema |
| 工具结果只有字符串 | 可能包含图片、详情、usage 和更多元数据 |
| 没有最大轮数、超时和取消控制 | 生产实现需要完整的生命周期控制 |
| `trace` 最终一次性返回 | 通常边运行边发布事件给订阅者 |

因此，阅读本文件时不要把 `ScriptedProvider` 当成真正的大模型，也不要认为这个 `while True` 已经覆盖了所有生产问题。它只提炼了最核心的反馈回路：

```text
assistant tool call -> execute -> tool result -> next assistant response
```

## 13. 建议的阅读顺序

如果重新阅读源码，可以按这个顺序：

1. 先看 `demo()`，找到一次调用需要哪些对象。
2. 再看 `run_agent_loop()` 的初始化、Provider 请求和循环退出条件。
3. 回头看 `UserMessage`、`AssistantMessage`、`ToolResultMessage`，理解消息如何流动。
4. 看 `_execute_tool()`，理解同步/异步工具和异常转换。
5. 最后看 `ScriptedProvider` 和 `TraceEntry`，理解测试替身与观测信息。

最值得在源码中定位的三个位置是：

- `current_messages = [*context.messages, *prompts]`：建立本次模型上下文。
- `current_messages.append(result)`：把工具结果反馈给模型。
- `if not assistant.tool_calls: break`：没有工具调用时结束循环。

## 14. 如何验证自己的理解

在仓库根目录运行 demo：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s01_agent_loop/code.py
```

再运行本章测试：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s01_agent_loop.py
```

测试重点对应以下不变量：

- 工具结果必须出现在下一次 Provider 请求中。
- 输入的历史上下文不能被本次调用原地修改。
- `error` / `aborted` 响应中的工具调用不能执行。
- 未知工具和工具异常必须变成模型可见的错误结果。
- `length` 截断的工具调用不能执行。

## 总结

这份 `code.py` 讲的不是某个具体工具，而是 Agent 的最小控制结构：

```text
维护上下文
  -> 请求模型
  -> 读取 assistant 的 tool call
  -> 执行工具
  -> 追加 tool result
  -> 再请求模型
  -> 直到 assistant 不再请求工具
```

只要掌握了三件事，整份代码就基本清楚了：

1. `AssistantMessage` 负责表达模型想说什么，尤其是它想调用什么工具。
2. `ToolResultMessage` 负责把程序执行结果重新交给模型。
3. `run_agent_loop()` 负责按顺序维护上下文并决定是否继续。
