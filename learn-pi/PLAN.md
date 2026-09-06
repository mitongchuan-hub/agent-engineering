# Learn Pi 建设计划

> 完整系统边界与分组见 [`SYSTEMS.md`](SYSTEMS.md)。  
> 上游事实真源：`agent-source/pi` @ `9767ba275f3e9a5ee0f5c5342249b629ab1b2282`  
> 教学实现：Python 3.12，默认完全离线

## 目标

课程聚焦 Coding Agent 内核：模型响应如何驱动工具调用、工具结果如何回到上下文，以及循环如何安全停止。CLI 解析和界面启动不进入主线。

这不是通用 Agent 教程，也不是逐行移植 Pi。每章从 Pi 固定提交的真实调用链中抽取一个稳定机制，再用小型 Python 实验验证它。

## 主线章节

| 章 | 目录 | 核心问题 | Pi 源码入口 | 状态 |
|---|---|---|---|---|
| 01 | `s01_agent_loop` | prompt、assistant、tool result 如何形成最小闭环 | `agent-loop.ts::runAgentLoop`、`runLoop` | 已完成 |
| 02 | `s02_provider_stream` | 完整响应如何变成可消费的增量流 | `streamAssistantResponse`、`ai/EventStream` | 已完成 |
| 03 | `s03_agent_events` | Agent 状态如何由事件协议驱动 | `agent.ts`、`types.ts::AgentEvent` | 已完成 |
| 04 | `s04_tool_contract` | 工具查找、参数准备、Schema 校验与错误结果如何工作 | `prepareToolCall`、`validateToolArguments` | 已完成 |
| 05 | `s05_parallel_tools` | 并行执行、完成顺序、落位顺序与截断保护如何兼容 | `executeToolCallsParallel`、相关测试 | 已完成 |
| 06 | `s06_message_queues` | steering 和 follow-up 消息在何时进入循环 | `PendingMessageQueue`、`runLoop` | 已完成 |
| 07 | `s07_control_boundaries` | stop、abort、error、terminate 和 settled 的边界是什么 | `agent.ts`、`agent-loop.ts` | 已完成 |
| 08 | `s08_context_boundary` | 应用消息如何裁剪并转换为模型消息 | `transformContext`、`convertToLlm` | 已完成 |
| 09 | `s09_session_memory` | Agent transcript 如何追加持久化并形成树形分支 | `agent-session.ts`、`session-manager.ts` | 已完成 |
| 10 | `s10_context_recovery` | 溢出、重试、压缩和分支摘要如何恢复上下文 | `core/compaction`、`agent-session.ts` | 已完成 |
| 11 | `s11_extension_boundary` | 自定义工具和资源如何进入 Agent，而不污染核心循环 | `resource-loader.ts`、扩展示例 | 已完成 |
| 12 | `s12_comprehensive` | 如何组合为模块化、可测试的最小 Coding Agent | 前 11 章稳定契约 | 已完成 |

CLI、print/json/RPC、SDK 和完整 Runtime 装配只作为附录解释产品接入方式，不占用 Agent 主线章节。

## 每章交付合同

每章必须包含：

- `README.md`：中文讲义、真实调用链、实验步骤和简化边界。
- `code.py`：独立运行，默认使用脚本化 Provider。
- `architecture.svg`：只画本章已实现对象及数据方向。
- 固定提交源码链接：每个关键结论可回溯到文件和符号。
- 离线测试：覆盖主路径和至少一个非直觉边界。

README 固定结构：本章问题、源码调用链、最小实现、动手实验、测试、简化边界、源码证据、下一章。

## 系统分组

本计划的六个系统、源码边界、依赖关系、完成标准和非目标统一记录在 [`SYSTEMS.md`](SYSTEMS.md)。本文件只维护章节实施顺序和状态。

| 系统 | 章节 | 当前状态 |
|---|---|---|
| Agent 执行核心 | `s01-s04` | 已完成 |
| 工具编排与运行控制 | `s05-s07` | 已完成 |
| 上下文与会话记忆 | `s08-s09` | 已完成 |
| 上下文恢复 | `s10` | 已完成 |
| 扩展与资源 | `s11` | 已完成 |
| 综合 Coding Agent | `s12` | 已完成 |

## 实施阶段

按系统依赖实施：

1. 完成 Agent 执行核心（`s01-s04`）。
2. 完成工具编排与运行控制（`s05-s07`）。
3. 完成上下文、Session 和恢复（`s08-s10`）。
4. 完成扩展与资源系统（`s11`）。
5. 完成综合 Coding Agent（`s12`）。
6. 最后实现课程 Web，直接读取 `course.json` 和 `sNN_*` 真源。

## 验收门槛

单章完成需同时满足：

- `code.py` 可在 `agent-engineering` Conda 环境直接运行。
- 无 API Key 时测试全部通过。
- 测试名称明确表达对应的 Pi 行为。
- 架构图和代码一致，没有未实现组件。
- README 明确区分 Pi 原始行为与教学简化。

全课程最终执行：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests
```

并完成 Web 类型检查、构建、链接和桌面/移动视口检查。

## 当前迭代：课程已完成

第 01-12 章、6 个系统和 Web 阅读器均已完成。当前只保留全量测试、源码链接、文档导航和 Web 构建作为持续验收项。
