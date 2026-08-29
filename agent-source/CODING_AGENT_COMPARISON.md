# 四大 Coding Agent 源码对比分析（学习笔记）

> 对比对象：openai/codex（Rust）、deepseek-ai/deepseek-harness（TS）、
> earendil-works/pi（TS）、anthropics/claude-code（提示词生态，核心闭源）
> 源码位置：`D:/work/xiangmu/agent-source/`
> 视角：与我们手写的 mini_agent（matcher-app）做横向参照

---

## 0. 一句话总览

| | codex | deepseek-harness | pi | claude-code |
|---|---|---|---|---|
| 语言 | Rust（monorepo 100+ crates） | TypeScript（monorepo 60+ 包） | TypeScript（10 包） | 提示词/Markdown（核心闭源） |
| 循环模型 | 事件驱动 Session + InputQueue | turn/step 状态机 + Inbox | 双层 while + 事件流 | 提示词编排多 agent |
| 扩展方式 | 插件 + hooks + MCP | **一切皆插件**（cordis） | 扩展/技能/主题（TUI 级） | plugins + commands + skills |
| 特色 | 沙箱/审批/持久化最重 | 插件化最彻底，含 plan/goal | 轻量、AI 层模型无关、自带 evals | 提示词工程/技能生态最丰富 |
| 可读性 | ❌ 极难（工程巨兽） | ⚠️ 中等（包多） | ✅ 最适合精读 | ✅ 提示词写作圣经 |

---

## 1. Agent 主循环（自测必考"你的 agent 怎么跑"）

### pi — 最简单直白（和我们手写的结构最近）
`packages/agent/src/agent-loop.ts`（约 300 行，核心可读）：
```ts
// 外层循环：持续处理"用户中途发来的消息"（steering messages）
while (true) {
  // 内层循环：处理工具调用
  while (hasMoreToolCalls || pendingMessages.length > 0) {
    const message = await streamAssistantResponse(...);  // 流式调模型
    if (message.stopReason === "error" || ...) break;     // 错误/中断兜底
    // tools -> 执行 -> 回填 -> hasMoreToolCalls = true
  }
}
```
- 亮点：**事件驱动**（EventStream + emit）+ 支持 `agentLoopContinue`（恢复执行）+ 用户可中途注入消息打断
- 和我们 mini_agent 的映射：它的内层 while ≈ 我们的 `Agent.run` 主循环；它的事件流我们省略了

### deepseek-harness — 状态机 + 插件钩子，工程味最浓
`packages/core/agent-loop/src/agent.ts`：
```ts
private async turn(): Promise<boolean> {
  while (true) {                       // 一个 turn 内的 loop
    const decision = await this.preStep(target, { turn, step });
    // preStep 会 dispatch.waterfall("agent/pre-step", ...)
    //   插件可以在这一步拦截、改写消息（например安全审查）
    this.session.append("step/start", { turn, step });   // 会话日志
    const stepEnd = await this.step(...);                // 一次模型+工具
    this.session.append("step/end", { turn, step });
  }
}
// 驱动：while (await this.turn()) {}   —— 直到 turn 返回 false
```
- 亮点：**turn/step 两级状态机**；**Inbox 消息领取**（支持并发唤醒）；**dispatch.waterfall/serial 插件钩子**（agent/pre-step 可改写输入）；**全程结构化会话日志**（turn/start→step/start→step/end→turn/end）；错误结构化（`LlmError` / errorChain / UNKNOWN）
- 底层是 **cordis/koishi 系插件框架**（`ctx.effect`、`dispatch` 等，代码里可见）

### codex — 事件驱动 Session + 输入队列（最难读）
`codex-rs/core/src/session/mod.rs`（183KB）+ `agent/control.rs`（33KB）：
- `session.spawn()` 起后台循环，`session.submit(op)` 提交操作，`session.next_event()` 拉事件 → **生产级消息泵**架构
- `input_queue.rs`（24KB）维护用户输入队列，`step_activation.rs` 决定步骤激活
- `control.rs` 负责 **多 agent 转场控制**（agent registry/role、subagent 通知）
- 工具系统 tools/：`registry.rs` + `router.rs` + `parallel.rs`（并行工具调用）+ `orchestrator.rs`
- 亮点：submission/Op 模型、rollout 持久化（checkpoint 级）、approvals 审批流、sandboxing

### claude-code — 循环在闭源端，开源的是"剧本"
仓库里是 **plugins/**（如 `code-review`：manifest + 带 YAML 头的 md 指令）：
```
---
allowed-tools: Bash(gh issue view:*), Bash(gh pr view:*), mcp__github_inline_comment__*
description: Code review a pull request
---
1. Launch a haiku agent 检查 PR 状态...
2. Launch a sonnet agent 读 diff 摘要...
3. Launch 4 agents in parallel 独立评审，返回 issues...
```
- 亮点：**声明式工具白名单**（allowed-tools）+ 编排多 agent 剧本 = 提示词即软件
- 自测价值：这是"提示词工程上限"的公开样本

---

## 2. 工具系统对比

| | 注册 | 执行 | 特殊机制 |
|---|---|---|---|
| 我们 mini_agent | `@tool` 装饰器 + 签名自动生成 schema | `registry.call` + 异常回传 | 离线 schema、MCP 桥 |
| pi | 内置 read/bash/edit/write + 扩展注册 | 事件流推送 | harness 权限门槛 |
| deepseek | packages/core/tools + skill 包 | dispatch 钩子链 | 插件可包一层工具（改参/拦截） |
| codex | tools/registry.rs | router（分发）+ parallel（并发）+ orchestrator | **approvals 审批** + **sandboxing 沙箱** + 工具 namespace |

自测点：codex 的 `approvals.rs`（34KB）值得讲——工具按危险等级分片（读/写/执行/网络），超过阈值要用户批准；deepseek 的插件钩子=工具调用前可插拦截器。

## 3. 上下文管理对比

| | 压缩 | 记忆 |
|---|---|---|
| codex | `compact.rs`（本地+远程模型压缩、llm fallback）、context_window.rs | AGENTS.md、memories、checkpoint 持久化 |
| deepseek | packages/compaction、context | session-query、spill、goal 持久化 |
| pi | 文档 compaction.md + session-backends | 会话文件格式 |
| claude-code | 闭源 | **CLAUDE.md/AGENTS.md 约定**（社区标准） |

自测点：codex 的 compact 有 **model fallback**（主模型太贵/不可用时换便宜模型做摘要）——比我们 mini_agent 的窗口截断更进一步，这就是"生产级 vs 教学级"的差距。

## 4. 独有亮点（自测谈资）

- **codex**：Rust 性能、三套沙箱（linux-sandbox/bwrap、windows-sandbox-rs、sandboxing crate）、MCP 自研（mcp-server/rmcp-client/codex-mcp）、多 agent 角色
- **deepseek**："Everything is a Plugin"——webhook、subagent、plan、goal 都是插件；llm 包同时支持 deepseek / pi 协议（`llm-pi-ai`），模型无关
- **pi**：TUI+server+SDK 一体化，AI 层支持 bedrock/oauth/compat 多 provider，**自带 packages/evals 评测包**（和你的评测集思想一致！）
- **claude-code**：allowed-tools 白名单、多 agent 剧本、plugins 生态最成熟

## 5. 学习学习路线建议

| 目标 | 选谁 | 怎么学 |
|---|---|---|
| 看懂 agent 循环原理 | **pi**（或 deepseek agent-loop 包） | 300 行内看懂 loop + 事件流 |
| 学插件化架构 | **deepseek-harness** | 它 60+ 包都是围绕 cordis 插件的，看 core/agent-loop + hooks 包 |
| 学工程化/沙箱/审批 | **codex**（挑模块看不全读） | approvals / sandboxing / context_window / compact |
| 学提示词编排 | **claude-code** | 读 plugins/* 的 md 剧本，抄 allowed-tools 写法 |

## 6. 我们的 mini_agent 站在哪

对照结论（自测怎么自我定位）：
1. **循环结构**：我们的 while loop 本质和 pi 内层循环、deepseek step 一致——原理没差，缺的是事件流/turn 状态机/恢复机制
2. **差距项**：审批流、沙箱、并行工具、上下文压缩 fallback、会话持久化——这些是"生产级"的共同答案
3. **我们的亮点**：测试覆盖（15 单测 + 评测集）比很多开源项目还规范；MCP 协议从零实现（deepseek 的 mcp 包也是封装，我们理解更深）

> 简历写法建议："对比分析 codex/deepseek-harness/pi 源码（各 1 轮循环+工具系统），手写 Agent 框架覆盖其核心抽象：循环、schema、上下文预算、MCP"