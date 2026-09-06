# Learn Pi 系统规划

> 文档性质：课程系统总规划与范围基线  
> 当前状态：系统设计完成，章节按此基线实施  
> 上游事实真源：`agent-source/pi` @ `9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

## 一、规划原则

本课程借鉴 `learn-claude-code-main` 的系统分组方式，但不把 Claude Code 的功能清单直接搬到 Pi 上。

参考项目的 20 章本质上分成六个教学阶段：

1. 基础执行：Loop、Tool、Permission、Hooks。
2. 复杂任务：Todo、Subagent、Context Compact。
3. 记忆恢复：Memory、System Prompt、Error Recovery。
4. 长期运行：Task、Background、Cron。
5. 多 Agent 协作：Teams、Protocol、Autonomous、Worktree。
6. 外部能力与综合：Skills、MCP、Comprehensive。

Pi 课程也采用六个系统层次，但每个系统内部的章节由 Pi 固定提交的真实调用链决定。

```text
系统分组：便于理解整体架构
章节顺序：服从源码依赖和运行时调用链
代码实现：每章独立，默认离线，四套课程互不共享 Agent 内核
```

## 二、Pi 的实际代码边界

这不是对所有目录的平铺翻译，而是课程使用的源码边界：

| 源码区域 | 真实职责 | 课程处理方式 |
|---|---|---|
| `packages/agent` | Agent 状态、低层 loop、事件、工具调用、队列 | 主线系统 1、2 |
| `packages/ai` | Provider/API 类型、消息转换、EventStream、工具参数校验 | 主线系统 1、2、3 |
| `packages/coding-agent/src/core` | Runtime、Session、资源、压缩、模型运行时 | 主线系统 3、4、5 |
| `packages/coding-agent/src/extensions` 与 examples | 扩展注册、自定义工具、资源介入 | 主线系统 5 |
| `packages/coding-agent/src/modes`、`sdk.ts`、CLI | 产品接入和运行模式 | 附录，不进入 Agent 主线 |

`packages/agent/src/harness` 中没有接入 CLI 主路径的实验内容，不会被描述成 Pi 的默认 Agent 能力。

## 三、六个教学系统

### 系统 1：Agent 执行核心

**章节：** `s01-s04`  
**状态：** 已完成

**目标：** 建立从用户 prompt 到 assistant、tool call、tool result 再到下一次模型请求的闭环。

**包含机制：**

- `runAgentLoop` / `runLoop` 的最小轮次。
- Provider 增量事件和 `EventStream`。
- Agent 生命周期事件与状态归约。
- 工具查找、参数准备、Schema 校验和执行前阻止。

**系统输入：** user message、模型上下文、工具目录。  
**系统输出：** assistant message、tool result、生命周期事件和可观察 Agent 状态。

**完成标准：** 能离线运行完整的一次工具回环；能解释 partial message、最终结果、错误结果和事件监听器之间的边界。

**非目标：** CLI 解析、真实 API、并发工具、Session 落盘。

### 系统 2：工具编排与运行控制

**章节：** `s05-s07`  
**状态：** `s05` 已完成，`s06-s07` 待开始

**目标：** 处理一个 Agent 运行中多个调用、外部消息和中断信号同时出现时的控制问题。

**包含机制：**

- 并行工具、工具级 sequential、完成顺序和结果顺序。
- steering/follow-up 双队列及 `all` / `one-at-a-time` drain。
- stop、abort、error、length、terminate 和 settled 的区别。

**系统输入：** assistant tool-call batch、运行中用户消息、abort signal。  
**系统输出：** 稳定的工具结果顺序、可恢复的错误结果、确定的结束边界。

**完成标准：** 并行完成事件不破坏 transcript 顺序；队列在正确循环边界注入；abort 后 Agent 最终回到 idle。

**非目标：** 多 Agent 团队通信、后台任务调度。

### 系统 3：上下文与会话记忆

**章节：** `s08-s09`  
**状态：** 待开始

**目标：** 说明 Agent 内部消息如何变成模型可接受的上下文，以及 transcript 如何作为可恢复的会话记忆保存。

**包含机制：**

- `AgentMessage[]` 到 LLM `Message[]` 的转换边界。
- context transform、过滤 UI 消息和上下文快照。
- JSONL Session 追加写。
- `id` / `parentId` 树、导航、branch 和 fork。

**系统输入：** Agent transcript、上下文转换器、Session 文件。  
**系统输出：** 模型上下文、可导航的历史树和新分支。

**完成标准：** 能从 JSONL 重建当前分支；不会把 UI-only 消息错误发送给模型；分支不会改写原分支历史。

**非目标：** 自动压缩策略和远程数据库。

### 系统 4：上下文恢复系统

**章节：** `s10`  
**状态：** 待开始

**目标：** 在上下文窗口不足、Provider 失败或分支摘要需要重建时，让 Agent 继续工作。

**包含机制：**

- context overflow 检测。
- compaction 准备和执行。
- branch summarization。
- retry、重试消息和失败边界。

**系统输入：** 当前 Session 分支、token 预算、Provider 错误。  
**系统输出：** 压缩后的可用上下文、摘要消息或明确失败结果。

**完成标准：** 压缩不破坏分支结构；重试不重复写入错误的 assistant 状态；失败可以被测试桩稳定复现。

**非目标：** 训练模型、猜测闭源产品的恢复实现。

### 系统 5：扩展与资源系统

**章节：** `s11`  
**状态：** 待开始

**目标：** 解释自定义工具、扩展、skills、prompt templates、主题和上下文文件如何进入运行时，同时保持核心 loop 不被改写。

**包含机制：**

- `DefaultResourceLoader` 及资源发现。
- 自定义工具注册和工具池合并。
- 扩展事件/命令介入点。
- 资源失败、禁用和作用域边界。

**系统输入：** 项目目录、用户资源目录、显式扩展路径。  
**系统输出：** 解析后的资源目录、自定义工具和运行时配置。

**完成标准：** 扩展能力通过稳定接口进入 Agent；扩展加载失败有诊断；禁用扩展时核心 loop 仍可运行。

**非目标：** 把 Claude Code 的 MCP、权限弹窗或子 Agent 假装成 Pi 内核实现。Pi 有对应扩展或对接能力时只按真实证据说明。

### 系统 6：综合 Coding Agent

**章节：** `s12`  
**状态：** 待开始

**目标：** 将前五个系统组合成一个模块化、可测试、默认离线的 Coding Agent Harness。

**组合边界：**

```text
Provider/EventStream
        -> Agent Loop
        -> Tool Orchestrator
        -> Context/Session
        -> Recovery
        -> Resources/Extensions
```

**完成标准：**

- 核心 loop、工具调度、Session、压缩和扩展是独立模块。
- 可以用脚本 Provider 完成完整测试，不依赖 API Key。
- 真实 Provider 只是可选适配器，不改变核心协议。
- CLI、text/json/RPC/SDK 作为附录适配层接入，而不是反向污染核心。

## 四、章节实施表

| 章 | 章节 | 所属系统 | 关键 Pi 符号 | 主要测试边界 |
|---|---|---|---|---|
| 01 | 最小 Agent Loop | 系统 1 | `runAgentLoop`、`runLoop` | 工具回环、错误、length 截断 |
| 02 | Provider 流与 EventStream | 系统 1 | `EventStream`、`AssistantMessageEvent` | 完成事件、result、partial 替换 |
| 03 | Agent 状态与事件协议 | 系统 1 | `processEvents`、`runWithLifecycle` | listener settle、idle、失败补偿 |
| 04 | 工具契约与参数校验 | 系统 1 | `prepareToolCall`、`validateToolArguments` | 找不到、校验、阻止、异常 |
| 05 | 并行工具与结果顺序 | 系统 2 | `executeToolCallsParallel` | completion/source order、sequential |
| 06 | Steering / Follow-up 队列 | 系统 2 | `PendingMessageQueue`、`runLoop` | drain 模式、注入边界、优先级 |
| 07 | 控制与结束边界 | 系统 2 | `Agent.abort`、`finishRun` | abort、error、terminate、settled |
| 08 | 上下文转换边界 | 系统 3 | `transformContext`、`convertToLlm` | 过滤、裁剪、不可转换消息 |
| 09 | Session 记忆与树形历史 | 系统 3 | `SessionManager` | JSONL、parent、branch、fork |
| 10 | 压缩与上下文恢复 | 系统 4 | `prepareCompaction`、`compact` | overflow、retry、摘要、失败 |
| 11 | 扩展工具与资源 | 系统 5 | `DefaultResourceLoader` | 发现、禁用、失败、注册 |
| 12 | 综合 Coding Agent | 系统 6 | 前 11 章稳定契约 | 端到端离线运行和模块隔离 |

## 五、每个系统的交付物

每个章节目录包含 `README.md`、`code.py`、`architecture.svg`、测试和源码证据。每个系统完成时额外产出：

- 系统 README：说明系统边界、依赖和不负责的事情。
- 系统架构图：连接本系统内章节，不绘制未实现组件。
- 系统验收测试：至少一个跨章节场景。
- `course.json` 中的系统状态和章节状态。

## 六、仓库文件职责

| 文件 | 唯一职责 |
|---|---|
| `SYSTEMS.md` | 系统分组、边界、依赖、非目标和完成标准；本文件是系统规划真源 |
| `PLAN.md` | 章节执行顺序、当前迭代和交付合同 |
| `course.json` | Web 和脚本读取的机器可读目录 |
| `UPSTREAM.md` | 固定提交的源码定位和教学映射 |
| `sNN_*/` | 章节代码、讲义、图和测试 |

不在其他文件中复制完整系统规划。系统调整时先改本文件，再同步 `PLAN.md` 和 `course.json`。

## 七、当前基线

```text
已完成：系统 1 的 s01-s04；系统 2 的 s05-s07；系统 3 的 s08-s09
待实施：系统 4-s6
暂停条件：没有系统规划变更，不继续随意新增章节
```

下一步应从 `s06_message_queues` 开始，完成系统 2 后再进入上下文和 Session 系统。
