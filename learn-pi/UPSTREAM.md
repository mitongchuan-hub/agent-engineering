# Pi 上游源码证据

## 固定版本

- Repository: `https://github.com/earendil-works/pi`
- Commit: `9767ba275f3e9a5ee0f5c5342249b629ab1b2282`
- Local snapshot: `agent-source/pi`

所有课程断言以该提交为准。本机安装的 Pi 版本只用于行为核验，不作为课程源码来源。

## 第 01 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| 新 prompt 进入当前上下文，并先发出 Agent/turn/message 事件 | `packages/agent/src/agent-loop.ts` | `runAgentLoop`，约第 96-119 行 | 复制 prompt 到 `newMessages`，追加到 `currentContext.messages`，随后发出生命周期事件 |
| 工具回环由 `runLoop` 驱动 | `packages/agent/src/agent-loop.ts` | `runLoop`，约第 156-277 行 | 模型响应后检查 tool calls，写入 tool result，再决定是否继续下一轮 |
| assistant 的消息在模型边界形成并加入上下文 | `packages/agent/src/agent-loop.ts` | `streamAssistantResponse`，约第 279-407 行 | 消费 AssistantMessageEventStream，最终消息替换 partial message |
| `error` 和 `aborted` 不再执行工具 | `packages/agent/src/agent-loop.ts` | `runLoop`，约第 216-220 行 | 遇到这两类 stop reason 后发出 `turn_end`/`agent_end` 并返回 |
| 截断响应中的 tool call 不执行 | `packages/agent/src/agent-loop.ts` | `failToolCallsFromTruncatedMessage`，约第 350-407 行 | `length` 响应为每个调用生成错误 ToolResult |
| Agent 上下文包含 system prompt、消息和工具 | `packages/agent/src/types.ts` | `AgentContext`，约第 415-429 行 | 这是本章 `AgentContext` 的来源 |
| Agent 事件区分 agent、turn、message 和 tool execution 生命周期 | `packages/agent/src/types.ts` | `AgentEvent`，约第 431 行起 | 本章用 `TraceEntry` 做离线的可读投影 |
| 非直觉边界有上游测试覆盖 | `packages/agent/test/agent-loop.test.ts` | 工具回环和 length 截断测试 | 本章测试将这些行为压缩为 Python 可运行实验 |

## 第 02 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| EventStream 同时提供异步迭代和最终结果 Promise | `packages/ai/src/utils/event-stream.ts` | `EventStream`，约第 4-67 行 | 队列、waiting resolver、完成判断和 `result()` 分属两条消费路径 |
| 完成事件仍进入事件队列，完成后 push 被忽略 | `packages/ai/src/utils/event-stream.ts` | `push`，约第 21-35 行 | 先标记完成并解析结果，再投递当前事件；后续调用直接返回 |
| `done` 和 `error` 都是 assistant stream 的终止事件 | `packages/ai/src/utils/event-stream.ts` | `AssistantMessageEventStream`，约第 69-85 行 | 完成判断是事件类型，结果从最终消息提取 |
| 事件协议包含 start、文本/思考/工具调用更新和 done/error | `packages/ai/src/types.ts` | `AssistantMessageEvent`，约第 531-570 行 | 每类更新携带当前 partial；终止事件携带 final/error message |
| partial 在上下文中被替换，最终消息在 message_end 发出 | `packages/agent/src/agent-loop.ts` | `streamAssistantResponse`，约第 279-347 行 | start 追加 partial，中间事件替换最后一条，done/error 读取 `response.result()` |
| 工具按名称查找，参数先准备再校验，失败时不执行 | `packages/agent/src/agent-loop.ts` | `prepareToolCallArguments`、`prepareToolCall`，约第 593-675 行 | 缺失工具、校验异常、策略阻止和 abort 都返回 immediate outcome |
| 参数校验会复制并转换输入 | `packages/ai/src/utils/validation.ts` | `validateToolArguments`，约第 317-350 行 | `structuredClone` 后执行可选转换和 schema 检查 |
| 工具异常转成错误结果，工具结果保留调用身份 | `packages/agent/src/agent-loop.ts` | `executePreparedToolCall`、`createToolResultMessage`，约第 677-805 行 | 异常变成 error result，最终 message 带 toolCallId/toolName |
| 并行工具的完成事件按完成顺序，结果消息按 assistant 源码顺序 | `packages/agent/src/agent-loop.ts` | `executeToolCallsParallel`，约第 487-570 行 | 并发任务完成时发 execution_end，`Promise.all` 结果按输入数组重建 |
| 任意 sequential 工具会强制整个 batch 顺序执行 | `packages/agent/src/agent-loop.ts` | `executeToolCalls`，约第 409-423 行 | `hasSequentialToolCall` 与配置共同决定调度器 |
| 截断响应中的所有工具调用都不执行 | `packages/agent/src/agent-loop.ts` | `failToolCallsFromTruncatedMessage`，约第 350-407 行 | length stop 生成错误结果，允许模型重新发起 |

## 第 06 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| steering 和 follow-up 使用两个独立队列 | `packages/agent/src/agent.ts` | `PendingMessageQueue`、`steer`、`followUp`，约第 122-318 行 | 两类消息分别入队，并可配置 `all` / `one-at-a-time` |
| steering 在当前 turn 完成后注入下一次请求 | `packages/agent/src/agent-loop.ts` | `runLoop`，约第 156-277 行 | 内层循环处理 tool calls 和 steering，当前工具调用不会被跳过 |
| follow-up 只在 Agent 将自然停止时检查 | `packages/agent/src/agent-loop.ts` | `runLoop` 外层循环，约第 246-274 行 | 内层循环结束后才 drain follow-up，并继续下一轮 |

## 第 07 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| Agent 运行开始时设为 streaming，结束后清理运行态 | `packages/agent/src/agent.ts` | `runWithLifecycle`、`finishRun`，约第 486-538 行 | 创建 AbortController，执行异常进入失败生命周期，finally 清理并 resolve idle |
| Provider/运行器抛错会补发完整失败事件序列 | `packages/agent/src/agent.ts` | `handleRunFailure`，约第 511-527 行 | 生成 error/aborted assistant，再发 message、turn 和 agent 结束事件 |
| agent_end 监听器完成前 Agent 不回到 idle | `packages/agent/src/agent.ts` | `processEvents`、`finishRun`，约第 540-586 行 | 监听器 promise 被 await，`finishRun` 在 run finally 才执行 |
| Session 在 retry/compaction/continuation 后才发 agent_settled | `packages/coding-agent/src/core/agent-session.ts` | `_runAgentPrompt`、`_handlePostAgentRun`、`_emitAgentSettled`，约第 1690-1720 行 | agent.prompt 返回后仍可能继续处理，finally 才发 settled |
| agent_settled 表示没有自动后处理或排队续跑 | `packages/coding-agent/src/core/extensions/types.ts` | `AgentSettledEvent`，约第 740-743 行 | 类型注释明确区分 agent_end 与 fully settled |

## 第 08 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| transformContext 先运行，convertToLlm 后运行 | `packages/agent/src/agent-loop.ts` | `streamAssistantResponse`，约第 279-296 行 | 先得到 AgentMessage[] 变换结果，再转换为 LLM Message[] |
| 转换后的消息与原始 AgentContext 分离 | `packages/agent/src/agent-loop.ts` | `streamAssistantResponse`，约第 288-301 行 | LLM Context 使用转换结果，运行 transcript 仍保留原消息 |
| coding-agent 自定义消息按类型过滤或映射 | `packages/coding-agent/src/core/messages.ts` | `convertToLlm`，约第 148-187 行 | bash、custom、branchSummary、compactionSummary 分别处理，标准消息原样通过 |
| UI-only notification 不应进入模型请求 | `packages/agent/src/types.ts` | `AgentLoopConfig.convertToLlm` 注释，约第 149-178 行 | 契约明确要求过滤不能转换的通知/状态消息 |

## 第 09 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| Session v3 首行是 header，后续 entry 通过 id/parentId 形成树 | `packages/coding-agent/src/core/session-manager.ts` | `SessionHeader`、`SessionEntryBase`，约第 34-58 行 | header 保存版本/id/cwd，entry 保存 id、parentId 和 timestamp |
| 当前 leaf 决定活动路径，追加 entry 只创建当前 leaf 的子节点 | `packages/coding-agent/src/core/session-manager.ts` | `_appendEntry`、`appendMessage`，约第 1058-1082 行 | append-only 写入并推进 leaf，不修改旧 entry |
| buildSessionContext 沿 leaf 回溯并投影上下文 | `packages/coding-agent/src/core/session-manager.ts` | `buildSessionPath`、`buildSessionContext`，约第 329-496 行 | 只将当前分支路径转换为 AgentMessage |
| branch 只移动 leaf，getTree 重建完整树 | `packages/coding-agent/src/core/session-manager.ts` | `getTree`、`branch`，约第 1312-1381 行 | 旧路径保留，下一次 append 产生新的子分支 |
| fork 创建新 header 并复制非 header entries | `packages/coding-agent/src/core/session-manager.ts` | `forkFrom`，约第 1611-1662 行 | 新 Session id，通过 parentSession 记录来源 |
| JSONL 坏行被跳过而非阻塞全部加载 | `packages/coding-agent/src/core/session-manager.ts` | `parseSessionEntries`、`loadEntriesFromFile` | 逐行解析，无法解析的行返回空/跳过 |

## 第 10 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| token 估算使用 usage 或 chars/4 兜底 | `packages/coding-agent/src/core/compaction/compaction.ts` | `calculateContextTokens`、`estimateContextTokens`、`estimateTokens`，约第 118-220 行 | 优先使用有效 assistant usage，没有 usage 时估算消息成本 |
| 压缩切点避开 toolResult，并支持 split turn | `packages/coding-agent/src/core/compaction/compaction.ts` | `findCutPoint`，约第 300-430 行 | 只从 user/assistant 等合法消息中选切点，记录 turn prefix |
| prepareCompaction 只计算准备数据，不直接写 Session | `packages/coding-agent/src/core/compaction/compaction.ts` | `prepareCompaction`，约第 750-830 行 | 生成 firstKeptEntryId、待摘要消息、token 和前次 summary |
| compact 生成 summary 和压缩结果 | `packages/coding-agent/src/core/compaction/compaction.ts` | `compact`，约第 854-970 行 | summary、firstKeptEntryId 和 tokensBefore 交给 Session 层保存 |
| overflow 先压缩，再最多 retry 一次 | `packages/coding-agent/src/core/agent-session.ts` | `_checkCompaction`、`_runAutoCompaction`，约第 2112-2425 行 | 失败/截断响应从活动上下文移除，压缩后继续一次 |
| transient error 使用可取消的指数退避 retry | `packages/coding-agent/src/core/agent-session.ts` | `_prepareRetry`，约第 2894-2945 行 | retryAttempt、baseDelay 和 abort controller 控制重试 |
| branch summary 也是独立恢复摘要路径 | `packages/coding-agent/src/core/agent-session.ts` | branch summarization 调用链，约第 3116-3305 行 | 离开分支前生成摘要，供新路径理解被放弃工作 |

## 第 11 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| ResourceLoader 统一管理 extensions、skills、prompts、themes 和上下文文件 | `packages/coding-agent/src/core/resource-loader.ts` | `ResourceLoader`、`DefaultResourceLoader`，约第 24-54、196-320 行 | loader 对外提供资源快照和 reload 接口 |
| reload 先加载扩展，再载入资源路径并收集诊断 | `packages/coding-agent/src/core/resource-loader.ts` | `reload`，约第 388-546 行 | no* 开关、额外路径和资源诊断均在该流程合并 |
| 扩展可以通过 resources_discover 返回额外资源路径 | `packages/coding-agent/src/core/extensions/types.ts` | `ResourcesDiscoverEvent/Result`，约第 545-560 行 | 扩展不直接改写 loader，而是提供 paths |
| Session 启动后将扩展发现的路径交给 ResourceLoader | `packages/coding-agent/src/core/agent-session.ts` | `bindExtensions`、`extendResourcesFromExtensions`，约第 2460-2500 行 | resources_discover 结果经过 metadata 处理后调用 `extendResources` |
| 扩展 handler 的失败被隔离并记录 | `packages/coding-agent/src/core/extensions/runner.ts` | `emitResourcesDiscover`，约第 1200-1240 行 | 单个 handler 抛错不会阻止其他扩展返回资源 |
| 自定义工具通过 ExtensionAPI 注册 | `packages/coding-agent/src/core/extensions/types.ts` | `ExtensionAPI.registerTool`、`ToolDefinition`，约第 1242-1315 行 | 工具定义包含名称、描述、schema 和 execute |

## 第 12 章定位

| 课程结论 | 上游文件 | 符号/位置 | 证据说明 |
|---|---|---|---|
| 综合实现的核心边界来自 Agent Loop、工具、上下文、Session、恢复和扩展 | 本课程 `SYSTEMS.md` | 系统 1-6 | 组合章只连接前面已验证的契约，不新增隐藏内核 |
| Agent Loop 负责 prompt、assistant、tool result 的闭环 | `packages/agent/src/agent-loop.ts` | `runAgentLoop`、`runLoop` | 模型调用和工具结果推动下一轮 |
| 工具批处理需要同时保持完成顺序和结果源码顺序 | `packages/agent/src/agent-loop.ts` | `executeToolCallsParallel` | 并发执行后按输入顺序生成 tool result |
| Session 和恢复通过 compaction entry 保留可恢复历史 | `packages/coding-agent/src/core/session-manager.ts`、`compaction/compaction.ts` | `appendCompaction`、`prepareCompaction`、`compact` | 综合章的离线 adapter 只复用这些稳定边界 |
| 扩展通过 ResourceLoader/API 接入而不改写核心 loop | `packages/coding-agent/src/core/resource-loader.ts`、`core/extensions/types.ts` | `DefaultResourceLoader`、`ExtensionAPI` | 综合章把扩展注册工具后交给 ToolRegistry |

## 教学映射

本章把 `AssistantMessageEventStream` 抽象成 `Provider.complete()`，把 TypeBox schema 暂时抽象成 Python callable，把完整工具结果暂时抽象成字符串。这些替换只服务于理解循环，不代表 Pi 的生产类型设计。
