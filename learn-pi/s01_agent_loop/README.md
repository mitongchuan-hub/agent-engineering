# 第 01 章：最小 Agent Loop

## 本章问题

Pi 的 Agent 核心不是一个只会重复请求模型的 `while True`。一次真实轮次至少要处理三类消息：

```text
user prompt -> assistant response
                       |
                       +-- tool call -> tool result -> assistant response
```

本章只回答一个问题：**模型产生工具调用后，Agent 如何把工具结果放回上下文，再请求模型直到得到最终回答？**

## 源码调用链

固定提交中的主路径是：

```text
agentLoop()
  -> runAgentLoop()
     -> runLoop()
        -> streamAssistantResponse()
        -> 收集 assistant.content 中的 toolCall
        -> 执行工具并生成 toolResult
        -> 继续下一轮 streamAssistantResponse()
        -> agent_end
```

对应 Pi 源码：

- `runAgentLoop()` 把新 prompt 加入当前上下文，并发出 `agent_start`、`turn_start` 和用户消息事件。
- `runLoop()` 负责重复轮次；没有工具调用时结束，有工具调用时先执行工具，再进入下一轮。
- `streamAssistantResponse()` 在生产实现中消费 Provider 的事件流，并把最终 assistant message 放入上下文。
- `AgentContext` 保存 system prompt、transcript 和可用工具。

本章将生产实现里的流式 Provider 简化为一次返回完整 `AssistantMessage`。流事件会在第 02 章单独展开。

## 最小实现

`code.py` 有五个关键对象：

| 对象 | 作用 |
|---|---|
| `AgentContext` | 保存 system prompt、已有消息和工具目录 |
| `Provider` | 根据 `ModelRequest` 返回一个 assistant message |
| `Tool` | 以名称和执行函数描述工具 |
| `ToolResultMessage` | 将工具成功或失败结果作为模型输入 |
| `run_agent_loop()` | 组织 prompt、模型、工具和终止条件 |

本章的 `ScriptedProvider` 有意使用预先写好的响应序列：第一次返回 `read_file` 调用，第二次读取 tool result 后返回文本。这样可以在离线环境中观察闭环，而不把学习重点放在 API 凭据上。

## 动手运行

在仓库根目录执行：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s01_agent_loop/code.py
```

你会看到：

1. `agent_start` 和第一轮 `turn_start`。
2. 用户消息和第一个 assistant tool call。
3. `tool_execution_start`、`tool_execution_end` 以及 `toolResult`。
4. 第二次 Provider 请求和最终 assistant 文本。
5. `agent_end`。

脚本使用内存中的 `hello.py`，不会读取项目文件，也不会访问网络。

## 先读测试

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s01_agent_loop.py
```

测试刻意覆盖几个容易写错的行为：

- 工具结果必须进入下一次模型请求。
- 输入的已有上下文不能被本次调用原地修改。
- `error` / `aborted` assistant message 直接结束，不能执行其中的工具调用。
- 找不到工具和工具抛错都要变成模型可见的错误结果。
- `length` 截断响应中的工具调用绝不能执行，即使参数看起来完整。

## 与 Pi 的差异

| 本章教学实现 | Pi 生产实现 |
|---|---|
| Provider 一次返回完整消息 | Provider 返回 `AssistantMessageEventStream` |
| 工具顺序执行 | 默认可并行，也支持工具级/配置级顺序执行 |
| 只有 prompt 入口 | 还支持 continuation、steering 和 follow-up 队列 |
| 使用 Python callable | 使用带 TypeBox schema 的 `AgentTool` |
| 直接以字符串表示工具结果 | 结果包含文本/图片、details、usage 和终止提示 |
| 通过返回值结束 | 还要处理事件流结束、订阅者结算和 abort |

这些差异不是遗漏的实现承诺，而是后续章节的明确学习边界。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`runAgentLoop`、`runLoop`、`streamAssistantResponse`。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/types.ts)：`AgentContext`、`AgentTool`、`AgentEvent`。
- [`agent-loop.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent-loop.test.ts)：正常工具回环、错误结果和截断工具调用测试。

本地对应的逐条定位见项目根目录 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 02 章把完整消息替换成 Provider 增量事件，解释 partial assistant message 如何在 `message_start`、`message_update` 和 `message_end` 之间演进。
