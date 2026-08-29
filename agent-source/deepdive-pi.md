# DEEP DIVE: earendil-works/pi（TypeScript）

> 源码：`agent-source/pi/` ｜ 语言：TypeScript（npm workspaces，10 包）
> 定位：轻量全能 Coding Agent（TUI+Server+SDK 一体化），**最容易读懂的完整 Agent**
> 阅读难度：★★★（最适合作为读源码的第一站）

## 一、定位

pi 是我们这个系列（learn-mini-agent）最重要的"高级对照"：
它的 `agent-loop.ts` 结构和我们手写的循环几乎同构，但补上了
**事件流、并行工具、steering 消息、会话 JSONL 持久化、40+ 模型 provider**。
先读懂 pi，再回头看 codex/deepseek 就会轻松很多。

## 二、代码地图（按学习顺序）

| 顺序 | 文件 | 内容 | 优先级 |
|---|---|---|---|
| 1 | `packages/agent/src/agent-loop.ts` | 双层循环（22KB，核心中的核心） | ⭐ 必读 |
| 2 | `packages/agent/src/agent.ts` | Agent 门面：run/continue（18KB） | ⭐ |
| 3 | `packages/agent/src/types.ts` | 核心类型 + **StreamFn 契约** + 工具执行模式 | ⭐ 精读 |
| 4 | `packages/agent/src/harness/agent-harness.ts` | Harness（系统提示词/上下文组装） | 🔍 |
| 5 | `packages/agent/src/harness/session/` | 会话状态 + jsonl 持久化 | 🔍 |
| 6 | `packages/agent/src/harness/compaction/` | 上下文压缩（branch-summarization） | 🔍 |
| 7 | `packages/agent/src/harness/tools/` | bash/read/write/edit + file-mutation-queue | 🔍 |
| 8 | `packages/ai/src/providers/` | **40+ 模型 provider**（模型无关的答案） | 📖 浏览 |
| 9 | `packages/ai/src/api/` | 各协议实现（anthropic-messages/openai-responses/pi-messages…） | 📖 |
| 10 | `packages/evals/` | 评测套件（和我们 s06 同思路） | 📖 |

## 三、核心机制拆解

### ① StreamFn 契约（types.ts）——错误也能流式

```ts
export type StreamFn = (model, context, options?) => AssistantMessageEventStream;
// Contract:
// - Must NOT throw or reject on request/model/runtime failures
// - Failures must be encoded in the stream via protocol events and
//   a final AssistantMessage with stopReason "error" or "aborted" + errorMessage
```
**亮点**：pi 把"失败"也变成流里的事件（stopReason="error"/"aborted"），
而不是抛异常。这样上层可以统一按"流"处理，UI 能看到错误原因。
（对比：我们的 mini_agent 用 try/except 抛 LLMError——pi 的做法更先进）

### ② 工具执行模式：sequential / parallel（types.ts）

```ts
// "sequential": 工具一个接一个执行
// "parallel"  : 工具先 prepare（串行），再 execute（并发）
//   tool_execution_end 按完成顺序发；tool-result 消息仍按发起顺序回填
```
**两阶段并行**（prepare 串行 → execute 并发）+ 回填顺序保证 =
多工具调用不丢因果。codex 的 parallel.rs 也是同一思路，跨语言呼应。

### ③ steering 消息：用户中途打断

agent-loop.ts 的外层 while 里，`getSteeringMessages()` 拉取用户排队消息，
在下一轮注入——**用户可以在 Agent 干活时插话**，循环不会丢。

### ④ 模型无关 = 40+ provider

`packages/ai/src/providers/` 有 openai、anthropic、google、deepseek、kimi-coding、
moonshot、qwen、zai… **每个 provider 一个文件 + 一个 .models.ts 生成清单**。
我们 s03 的 ChatClient 是它的 1/40 缩小版——思路完全同源。

## 四、三档阅读路线

- **30 分钟**：`agent-loop.ts` 从头读到 runLoop 结束（约 150 行核心）
- **半天**：agent-loop + types.ts（StreamFn/事件类型）+ agent.ts，能画出事件流图
- **2 周**：harness 全目录（session/compaction/tools）+ ai/providers 挑 3 家对比，最后跑 `packages/evals` 看评测怎么挂

## 五、面试考点

1. "模型调用失败怎么处理？" → pi 把失败编码进流（stopReason），不抛异常
2. "Agent 循环有几种写法？" → 双层 while（pi）/ 状态机（deepseek）/ 事件泵（codex）
3. "并行工具怎么保证顺序？" → prepare 串行 + execute 并发 + 回填按发起序
4. "怎么做到模型无关？" → provider 层每个厂商一文件，协议适配层统一

## 六、动手练习

1. 数一下 `agent-loop.ts` 里 emit 了多少种事件类型，试着排个序（turn_start→message_start→…）
2. 把我们的 mini_agent 循环改造成"失败进流"风格（加 stopReason 字段）
3. 在 `packages/ai/src/providers/` 里找一个你没见过的模型（如 zai），看它的模型清单怎么生成的