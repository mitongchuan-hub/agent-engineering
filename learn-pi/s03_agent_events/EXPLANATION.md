# `code.py` 结构化解读：Agent 事件与状态归约

> 代码文件：[`code.py`](./code.py)
>
> 本章重点：第 02 章处理 Provider 产生的底层流式事件；本章再向上抽象一层，用 `Agent` 维护运行状态，并把事件通知给 UI、日志系统或其他订阅者。

## 1. 先记住一句话

本章的 `Agent` 不是另一个模型循环，而是：

```text
生命周期控制器 + 事件分发器 + 状态归约器
```

它接收低层 Runner 发出的事件：

```text
agent_start
turn_start
message_start / update / end
工具执行 start / update / end
turn_end
agent_end
```

然后对每个事件执行固定顺序：

```text
收到 AgentEvent
    |
    v
先更新 AgentState
    |
    v
再通知所有 listener
    |
    v
继续处理下一个事件
```

因此，listener 看到的是**事件发生之后的状态**，而不是旧状态。

## 2. 它解决了什么问题

前两章分别解决了：

- 第 01 章：模型调用工具后，如何继续 Agent Loop。
- 第 02 章：Provider 如何把一条回答拆成流式事件，并组装 partial message。

本章解决的是更上层的问题：

```text
谁保存当前 transcript？
谁知道 Agent 是否还在运行？
UI 如何知道当前正在生成什么？
UI 如何知道哪个工具正在执行？
发生异常时，如何保证生命周期完整结束？
```

对应架构：

```text
低层 Runner / Agent Loop
          |
          | emit(AgentEvent)
          v
        Agent
          |
          +-- reduce AgentState
          |
          +-- notify listeners
          |
          v
       UI / 日志 / 测试
```

## 3. 三类核心对象

本章主要围绕三个对象展开：

| 对象 | 作用 |
|---|---|
| `AgentEvent` | 描述发生了什么 |
| `AgentState` | 保存 Agent 当前状态 |
| `Agent` | 接收事件、更新状态、通知 listener、控制运行生命周期 |

可以用一个函数表达状态归约：

```python
new_state = reduce(old_state, event)
```

代码没有单独写一个 `reduce()` 函数，而是把归约逻辑放在：

```python
Agent._process_event()
```

## 4. 消息模型

### `UserMessage`

```python
UserMessage(text="hello.py")
```

表示用户输入，固定带有：

```python
role = "user"
```

### `AssistantMessage`

```python
AssistantMessage(
    text="文件内容是 hello from Pi",
    stop_reason="stop",
)
```

表示模型输出，包含：

- `text`：文本内容。
- `stop_reason`：停止原因，可以是 `stop`、`toolUse`、`error` 或 `aborted`。
- `error_message`：失败时的错误信息。

### `ToolResultMessage`

```python
ToolResultMessage(
    tool_call_id="call-1",
    tool_name="read_file",
    text="hello from Pi",
)
```

表示工具执行结果。`is_error` 可以标记工具是否执行失败。

三种消息合并为统一类型：

```python
Message = UserMessage | AssistantMessage | ToolResultMessage
```

## 5. `AgentEvent`：事件协议

```python
@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: EventType
    message: Message | None = None
    messages: tuple[Message, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    partial_result: str | None = None
    is_error: bool = False
    tool_results: tuple[ToolResultMessage, ...] = ()
```

`AgentEvent` 是一个统一的事件对象。不同事件使用不同字段，不需要每种事件都定义一个单独的 Python class。

### 5.1 Agent 生命周期事件

```text
agent_start
    一次 Agent 运行开始

agent_end
    一次 Agent 运行即将结束，可能附带完整消息

turn_start
    一轮模型处理开始

turn_end
    一轮模型处理结束
```

### 5.2 消息生命周期事件

```text
message_start
    一条消息开始生成或开始进入 transcript

message_update
    当前消息的 partial 快照发生变化

message_end
    一条消息最终完成
```

消息可以是用户消息、assistant 消息或工具结果。

### 5.3 工具执行事件

```text
tool_execution_start
    工具开始执行，携带调用 id 和工具名

tool_execution_update
    工具执行过程中的进度信息

tool_execution_end
    工具执行结束
```

例如：

```python
AgentEvent(
    "tool_execution_update",
    tool_call_id="call-1",
    tool_name="read_file",
    partial_result="reading hello.py",
)
```

这里的 `partial_result` 是工具过程中的进度，不是最终 `ToolResultMessage`。

## 6. `AgentState`：Agent 当前状态

```python
@dataclass(slots=True)
class AgentState:
    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    streaming_message: Message | None = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error_message: str | None = None
```

每个字段的含义：

| 字段 | 含义 |
|---|---|
| `system_prompt` | Agent 配置中的系统提示词，本章没有实际发送给模型 |
| `messages` | 已经结束、可以进入 transcript 的消息 |
| `is_streaming` | 当前 Agent 是否处于活跃运行状态 |
| `streaming_message` | 当前还没有结束的消息快照 |
| `pending_tool_calls` | 正在执行的工具调用 id 集合 |
| `error_message` | 最近一次运行错误信息 |

最容易混淆的是 `messages` 和 `streaming_message`：

```text
messages
    只保存已完成消息

streaming_message
    保存当前正在生成的临时消息
```

例如 assistant 正在生成：

```text
messages           = [user]
streaming_message  = assistant 的当前 partial
```

assistant 结束后：

```text
messages           = [user, assistant]
streaming_message  = None
```

## 7. `AbortSignal`：简单的中止信号

```python
class AbortSignal:
    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True
```

它是一个简化版的取消信号：

```python
agent.abort()
```

会把本次运行的 signal 标记为：

```python
signal.aborted == True
```

但它不会强行杀掉正在运行的 Python 函数。Runner 或工具必须主动检查这个标志，并决定停止。

本章的 `ScriptedRunner` 会在发送每个事件前检查：

```python
if signal.aborted:
    raise RuntimeError("run aborted")
```

因此这是一个**协作式中止**机制。

## 8. 三种函数类型

### `AgentListener`

```python
AgentListener = Callable[
    [AgentEvent, AbortSignal],
    None | Awaitable[None],
]
```

listener 可以是同步函数，也可以是异步函数。它接收：

- 当前事件。
- 本次运行的 abort signal。

典型用途：

- 更新 UI。
- 打印日志。
- 保存事件。
- 监听工具进度。

### `EventSink`

```python
EventSink = Callable[[AgentEvent], Awaitable[None]]
```

`EventSink` 是 Runner 用来发事件的函数，也就是：

```python
await emit(event)
```

这里的 `emit` 实际上会指向 Agent 的：

```python
_process_event()
```

### `Runner`

```python
Runner = Callable[
    [str, EventSink, AbortSignal],
    Awaitable[None],
]
```

Runner 负责底层执行流程并产生事件。它可以是真实的 Agent Loop，也可以是测试桩。

它不直接修改 Agent 的状态，而是通过 `emit()` 把事件交给 Agent。

## 9. `Agent` 初始化做什么

```python
agent = Agent(runner, initial_state=None)
```

初始化时会：

1. 保存 Runner。
2. 复制初始消息列表。
3. 创建空的 listener 列表。
4. 初始化运行状态。
5. 准备后续使用的 signal 和 idle future。

这里复制初始列表：

```python
messages=list(initial.messages)
```

是为了避免外部调用者继续通过原来的列表绕过 Agent 的状态边界。

## 10. `subscribe()`：订阅事件

```python
unsubscribe = agent.subscribe(listener)
```

注册 listener 后，Agent 每收到一个事件都会通知它。

`subscribe()` 返回一个取消订阅函数：

```python
unsubscribe()
```

取消函数是幂等的，调用一次或多次都不会出错。

注册 listener 时不会立即发送当前状态，也就是说：

```text
subscribe(listener)
    不会自动收到 agent_start 之前的历史事件
```

### listener 的执行顺序

多个 listener 按注册顺序执行：

```text
listener 1
    |
listener 2
    |
listener 3
```

代码使用：

```python
for listener in tuple(self._listeners):
```

遍历当前 listener 的快照，避免 listener 在通知过程中修改原列表影响本轮遍历。

## 11. `prompt()`：一次运行的生命周期

```python
await agent.prompt("hello.py")
```

这是 Agent 对外的主要入口。

### 11.1 防止并发 prompt

```python
if self._active:
    raise RuntimeError("Agent is already processing a prompt...")
```

同一个 Agent 同时只能处理一个 prompt。本章没有实现消息队列；如果已有运行还没结束，第二次调用会直接报错。

后续章节会用队列处理 steering 和 follow-up 消息。

### 11.2 开始运行

进入运行后，代码创建本次专属状态：

```python
self._active = True
self._signal = AbortSignal()
self._idle_future = loop.create_future()
self.state.is_streaming = True
self.state.streaming_message = None
self.state.error_message = None
```

可以理解为：

```text
Agent 从 idle 进入 active
```

此时：

- `is_streaming=True`
- 有一个新的 abort signal
- 有一个表示“运行完成”的 future
- 清空上一次的临时消息和错误信息

### 11.3 运行 Runner

```python
await self._runner(
    text,
    self._process_event,
    self._signal,
)
```

Agent 把三个东西交给 Runner：

```text
用户 prompt
事件发送函数 emit
本次运行的 signal
```

Runner 通过：

```python
await emit(event)
```

向 Agent 报告进度。

### 11.4 统一处理 Runner 异常

如果 Runner 抛出异常：

```python
except Exception as error:
    await self._handle_run_failure(error, self._signal.aborted)
```

Agent 不会只让异常裸奔出去，而是补发一套完整的失败事件：

```text
message_start  error assistant
message_end    error assistant
turn_end       error assistant
agent_end      error assistant
```

这样 UI 和日志系统不需要额外猜测“为什么突然没有后续事件了”，所有失败都能按照统一生命周期收尾。

## 12. `_process_event()`：先归约，再通知

这是本章最核心的方法：

```python
async def _process_event(self, event: AgentEvent) -> None:
```

它严格遵循：

```text
第一步：根据事件更新 AgentState
第二步：按顺序执行所有 listener
```

### 12.1 消息事件如何更新状态

```python
if event.type in {"message_start", "message_update"}:
    self.state.streaming_message = event.message
```

收到开始或更新事件时，当前消息仍然没有结束，所以放入：

```python
state.streaming_message
```

收到结束事件时：

```python
elif event.type == "message_end":
    self.state.streaming_message = None
    if event.message is not None:
        self.state.messages.append(event.message)
```

状态变化是：

```text
message_start
    streaming_message = 当前消息

message_update
    streaming_message = 新的 partial

message_end
    streaming_message = None
    messages.append(最终消息)
```

### 12.2 工具事件如何更新状态

工具开始：

```python
self.state.pending_tool_calls.add(event.tool_call_id)
```

工具结束：

```python
self.state.pending_tool_calls.discard(event.tool_call_id)
```

因此：

```text
tool_execution_start
    pending_tool_calls = {"call-1"}

tool_execution_end
    pending_tool_calls = set()
```

使用 `set` 的原因是：

- 一个调用 id 只需要记录一次。
- 可以快速判断某个调用是否还在执行。
- 工具结束时使用 `discard`，即使 id 不存在也不会报错。

### 12.3 错误状态如何更新

```python
elif event.type == "turn_end":
    if isinstance(event.message, AssistantMessage):
        if event.message.error_message:
            self.state.error_message = event.message.error_message
```

错误信息在带错误 assistant message 的 `turn_end` 时写入状态。

### 12.4 `agent_end` 做什么

```python
elif event.type == "agent_end":
    self.state.streaming_message = None
```

它确保 Agent 结束时不会残留正在生成的消息。

注意：`agent_end` 本身不会立即把 `is_streaming` 改为 `False`。真正清理运行态是在所有 listener 完成以后执行的 `_finish_run()`。

## 13. 为什么一定要“先更新状态，再通知 listener”

假设事件是：

```python
AgentEvent("tool_execution_start", tool_call_id="call-1")
```

代码先把 `call-1` 加入：

```python
state.pending_tool_calls
```

然后才调用 listener。

所以 listener 里读取状态时可以得到：

```python
{"call-1"}
```

而不是空集合。

对于 `message_end` 也是一样：listener 执行时，最终消息已经被追加到 `state.messages`。

这保证了事件和状态的一致性：

```text
listener 收到 event
    同时看到 event 生效后的 state
```

## 14. `_finish_run()`：什么时候才算真正 idle

```python
def _finish_run(self) -> None:
```

它负责清理一次运行产生的临时状态：

```python
self.state.is_streaming = False
self.state.streaming_message = None
self.state.pending_tool_calls.clear()
self._active = False
```

然后完成等待中的 future：

```python
self._idle_future.set_result(None)
```

最后清除运行引用：

```python
self._idle_future = None
self._signal = None
```

真正的生命周期是：

```text
prompt 开始
    is_streaming = True
        |
        v
Runner 发出事件
        |
        v
agent_end 事件发出
        |
        v
等待所有 agent_end listener 完成
        |
        v
_finish_run()
    is_streaming = False
    wait_for_idle() 完成
```

### `agent_end` 不等于已经 idle

在 `agent_end` listener 执行期间：

- `is_streaming` 仍然是 `True`。
- `wait_for_idle()` 仍然不会完成。
- listener 可以做最后的保存、渲染或清理工作。

只有 listener 全部返回后，Agent 才真正 idle。

## 15. `wait_for_idle()` 的作用

```python
await agent.wait_for_idle()
```

它用于等待当前运行完全结束。

如果当前没有运行：

```python
self._idle_future is None
```

函数会立即返回。

如果当前有运行，就等待 `_finish_run()` 完成 future。这比单纯等待 Runner 结束更严格，因为它还包含了 `agent_end` listener 的异步收尾时间。

## 16. `ScriptedRunner`：低层 Runner 测试桩

```python
class ScriptedRunner:
    def __init__(self, events, *, delay=0.0):
        self.events = tuple(events)
```

它不会调用真实模型，也不会真正执行工具，只按顺序发送固定事件：

```python
for event in self.events:
    if signal.aborted:
        raise RuntimeError("run aborted")
    await emit(event)
    if self.delay:
        await asyncio.sleep(self.delay)
```

它的作用是：

- 离线测试生命周期。
- 确定事件顺序。
- 测试 listener 看到的状态。
- 测试异常、中止和并发行为。

真实系统中，Runner 可以替换成第 01、02 章中更完整的 Agent Loop，而 `Agent` 本身不需要知道事件具体是怎么产生的。

## 17. `demo_events()` 的完整事件序列

`demo_events("hello.py")` 构造了一个包含一次工具调用的完整过程：

```text
agent_start
turn_start

message_start(user)
message_end(user)

message_start(assistant partial)
message_update(assistant updated)
message_end(assistant)

tool_execution_start(read_file)
tool_execution_update(reading hello.py)
tool_execution_end(read_file)

message_start(toolResult)
message_end(toolResult)
turn_end

turn_start
message_start(final assistant)
message_end(final assistant)
turn_end

agent_end
```

最终 transcript 是：

```text
1. user        hello.py
2. assistant   我先读取文件
3. toolResult  hello from Pi
4. assistant   文件内容是 hello from Pi
```

这里的 `demo_events()` 只是模拟低层 Agent Loop 已经做完的工作。它没有在本章里真正查找或执行 `read_file`。

## 18. `demo()` 如何观察状态

```python
agent = Agent(ScriptedRunner(demo_events("hello.py")))
```

然后注册一个异步 listener：

```python
async def listener(event, _signal):
    observed.append(event.type)
    if event.type == "tool_execution_start":
        print(agent.state.pending_tool_calls)
```

因为 Agent 会先归约状态，再执行 listener，所以在 `tool_execution_start` listener 中已经能看到：

```text
['call-1']
```

运行结束后：

```text
is_streaming: False
pending_tool_calls: []
messages: 4
final: 文件内容是 hello from Pi
```

这说明：

- Agent 已回到 idle。
- 工具调用集合已经清空。
- 四条完成消息已经进入 transcript。
- 最后一条是最终 assistant 回答。

## 19. 错误流程

如果 Runner 在中途抛出：

```python
raise RuntimeError("provider exploded")
```

`prompt()` 会捕获它，并生成一条失败的 assistant message：

```python
AssistantMessage(
    text="",
    stop_reason="error",
    error_message="provider exploded",
)
```

然后补发：

```text
message_start
message_end
turn_end
agent_end
```

如果 signal 已经被 abort，则失败消息的停止原因是：

```text
aborted
```

这样无论正常结束还是异常结束，订阅者都能收到一套完整的收尾事件。

## 20. 并发和取消边界

### 同一个 Agent 不允许并发 prompt

```python
first = asyncio.create_task(agent.prompt("first"))
await agent.prompt("second")
```

第二次调用会抛出：

```text
Agent is already processing a prompt
```

当前实现没有排队策略。要支持多个输入，需要在更上层增加队列。

### `abort()` 是协作式的

```python
agent.abort()
```

只会设置 signal：

```python
signal.aborted = True
```

Runner、工具或 Provider 需要主动检查它。它不会自动取消所有正在执行的工作。

### listener 的异步等待属于运行的一部分

如果 listener 在 `agent_end` 中执行：

```python
await release.wait()
```

那么：

- `agent.prompt()` 不会立即完成。
- `agent.wait_for_idle()` 也不会完成。
- `state.is_streaming` 仍然是 `True`。

这保证了外部观察者有时间完成最终处理。

## 21. 与第 02 章的关系

第 02 章处理的是 Provider 级别的事件：

```text
start
text_delta
text_end
done
```

第 03 章处理的是 Agent 级别的生命周期事件：

```text
agent_start
turn_start
message_start/update/end
tool_execution_start/update/end
turn_end
agent_end
```

两层关系可以表示为：

```text
Provider stream event
        |
        v
Agent Loop / Runner 转换
        |
        v
AgentEvent
        |
        v
AgentState + listeners
```

第 02 章关心“模型回答如何生成”；第 03 章关心“整个 Agent 运行如何被外部观察和管理”。

## 22. 容易混淆的几点

### `AgentEvent` 不是 `AgentState`

```text
AgentEvent：发生了什么
AgentState：现在是什么状态
```

例如：

```text
AgentEvent("tool_execution_start", call-1)
```

会导致：

```text
AgentState.pending_tool_calls = {"call-1"}
```

### `message_end` 才会写入完整 transcript

`message_start` 和 `message_update` 只更新：

```python
streaming_message
```

只有 `message_end` 才追加到：

```python
messages
```

### `agent_end` 不是最终消息

最终 assistant 消息通常已经在此前的 `message_end` 中写入。`agent_end` 表示整次 Agent 运行进入收尾阶段。

### Runner 不直接改变 Agent 状态

Runner 只负责：

```python
await emit(event)
```

状态变化统一由 Agent 的 `_process_event()` 完成，这样状态更新规则只有一个地方。

## 23. 建议的阅读顺序

重新阅读源码时可以按下面的顺序：

1. 先看 `demo()`，了解最终输出。
2. 看 `demo_events()`，列出一次运行的完整事件顺序。
3. 看 `AgentState`，明确每个状态字段。
4. 看 `_process_event()`，建立事件到状态的映射。
5. 看 `prompt()` 和 `_finish_run()`，理解运行开始与结束。
6. 看 `subscribe()`、`wait_for_idle()`、`abort()`，理解外部控制能力。
7. 最后看 `ScriptedRunner` 和 `_handle_run_failure()`，理解测试和异常场景。

最值得记住的三段逻辑是：

```python
await self._runner(text, self._process_event, self._signal)
```

Runner 通过 Agent 的事件入口报告执行过程。

```python
# 先更新 state，再执行 listener
```

监听器读取到的是最新状态。

```python
self._finish_run()
```

所有结束事件和 listener 完成后，Agent 才真正回到 idle。

## 总结

第 03 章建立的是 Agent 的“可观察外壳”：

```text
Runner 产生事件
    -> Agent 归约 AgentState
    -> Agent 通知 listeners
    -> agent_end 后等待收尾
    -> 清理运行态并进入 idle
```

一句话记忆：

> `AgentEvent` 描述变化，`AgentState` 保存结果，`Agent` 负责先归约状态、再通知外部，并完整管理一次运行的生命周期。

验证命令：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s03_agent_events/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s03_agent_events.py
```
