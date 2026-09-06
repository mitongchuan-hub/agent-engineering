# 第 08 章：上下文转换边界

## 本章问题

Agent 运行时保存的消息不一定都应该发送给模型。Pi 将这件事拆成两个可替换的阶段：

```text
AgentMessage[]
    -> transformContext()  # 裁剪、注入、上下文管理
    -> convertToLlm()      # 类型转换、过滤、协议适配
    -> LLM Message[]
```

本章不实现压缩算法，只固定两个函数的边界和调用顺序。

## 源码调用链

```text
runLoop()
  -> streamAssistantResponse()
     -> transformContext(context.messages)
     -> convertToLlm(messages)
     -> Context { systemPrompt, messages, tools }
     -> Provider
```

`transformContext` 工作在完整的 `AgentMessage` 层，可以裁剪旧消息或注入外部上下文；`convertToLlm` 工作在协议边界，把自定义消息转换为 user/assistant/toolResult，或过滤 UI-only 消息。

## 消息类型

本章覆盖 Pi coding-agent 中最重要的自定义消息：

- `notification`：只供 UI 使用，过滤掉。
- `bashExecution`：通常转成 user 文本；`excludeFromContext` 时过滤。
- `custom`：扩展注入的消息转成 user。
- `branchSummary`：带 summary 标记转成 user。
- `compactionSummary`：带 summary 标记转成 user。
- `user`、`assistant`、`toolResult`：原样保留。

完整 transcript 和模型上下文因此可能不同，这是设计目标，不是数据丢失。

## 最小实现

```python
llm_context, traces = await build_llm_context(
    agent_context,
    transform_context=lambda messages: keep_last(messages, 10),
)
```

实现有两个重要特征：

1. `transform_context` 的输出才会交给 converter。
2. 每次构建模型请求都会重新执行 transform 和 convert；不要把一次转换结果永久当作 transcript。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s08_context_boundary/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s08_context_boundary.py
```

示例会同时打印 Agent transcript 的角色和模型实际看到的角色。通知消息保留在前者，但不会出现在后者。

## 关键测试

- transform 一定先于 converter。
- converter 只能看到 transform 后的列表。
- transform 不改变 Agent transcript 容器。
- notification 和排除上下文的 bash 消息被过滤。
- tool result 仍然对模型可见且顺序不变。
- branch/compaction summary 转成带标记的 user context。
- 两个阶段都支持异步函数。
- 每次模型请求都会重新执行 transform。
- transform 返回空列表是合法结果。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| 使用简单 dataclass 消息 | Pi 使用 LLM Message 和可扩展 AgentMessage 联合类型 |
| `convert_to_llm` 覆盖少量 coding-agent 消息 | Pi 还携带图片内容、时间戳和更多类型字段 |
| `keep_last` 按消息条数裁剪 | Pi 的上下文管理会结合 token、工具结果和压缩策略 |
| 工具目录只保存名称 | Pi 传递完整工具 schema |
| 不执行 Provider 请求 | `streamAssistantResponse` 将结果送入真实流式 Provider |

压缩、Session 树和恢复逻辑分别属于第 09、10 章。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：`streamAssistantResponse` 中 transform、convert 和 LLM Context 的顺序。
- [`types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/types.ts)：`AgentMessage`、`AgentContext` 和 `AgentLoopConfig` 的转换契约。
- [`messages.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/messages.ts)：`BashExecutionMessage`、`CustomMessage`、summary 消息和 `convertToLlm`。
- [`agent-loop.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/test/agent-loop.test.ts)：custom message 过滤和 transform-before-convert 测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 09 章实现 JSONL Session 和树形历史，让 transcript 具备追加持久化、分支和 fork 能力。
