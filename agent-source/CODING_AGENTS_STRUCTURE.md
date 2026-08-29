# 四大 Coding Agent 组成结构详解

> 源码：`D:/work/xiangmu/agent-source/`（真实 GitHub 克隆，2026-08 快照）
> 对象：openai/codex（Rust）、deepseek-ai/deepseek-harness（TS）、earendil-works/pi（TS）、anthropics/claude-code（提示词生态）
> 阅读方式：每章独立；所有路径/行数为真实数据，可打开对照

---

# 一、openai/codex —— Rust 生产级巨兽

## 1.1 概览

| 项 | 值 |
|---|---|
| 语言/构建 | Rust（Cargo + Bazel 并存，`BUILD.bazel`） |
| 规模 | monorepo，`codex-rs/` 下 **100+ crates**，核心文件 6750 个 |
| 架构风格 | 事件驱动 Session + 消息队列 + 多 agent 角色 |
| 入口 | `codex-rs/cli/`（CLI）、`codex-rs/core/`（引擎）、`codex-rs/app-server-daemon/`（后台服务） |

## 1.2 核心引擎分层（codex-rs/core/src）

```
core/src
├── client.rs            111KB  会话客户端：核心对话循环 + 提交/事件分发
├── codex_thread.rs       36KB  线程模型（thread = 一次持续性会话）
├── compact.rs            30KB  上下文压缩（本地/远程模型、token 预算）
├── compact_model_fallback.rs   压缩时主模型不可用→回退便宜模型
├── elicitation.rs              主动追问澄清
├── agents_md.rs         18KB  AGENTS.md 记忆文件解析
├── agent_communication.rs      子 agent 消息通道
├── session/             会话运行时（最重的一层）
│   ├── mod.rs           183KB  Session 主类型：spawn/submit/next_event
│   ├── input_queue.rs    24KB  用户输入队列（并发消息有序化）
│   ├── step_activation.rs      步骤激活决策
│   ├── mcp.rs / mcp_runtime.rs 65KB  MCP 服务器/客户端运行时
│   ├── context_window.rs       上下文窗口管理
│   ├── rollout_reconstruction.rs 81KB  回放重建（持久化恢复）
│   ├── session.rs        78KB  会话状态机
│   └── multi_agents.rs / review.rs
├── agent/               多 agent 控制
│   ├── control.rs        33KB  agent 转场控制（turn 级别）
│   ├── registry.rs / role.rs    agent 注册表 + 角色配置
├── tools/               工具系统
│   ├── registry.rs       31KB  工具注册表
│   ├── router.rs         13KB  按条件路由工具
│   ├── parallel.rs       27KB  并行工具执行
│   ├── orchestrator.rs   24KB  工具编排协调
│   ├── approvals.rs      34KB  危险操作审批流（工具分级）
│   ├── sandboxing.rs     19KB  工具沙箱策略
│   ├── spec_plan.rs      60KB  spec-driven 规划（planning 模式）
│   └── handlers/         具体工具实现
│       ├── apply_patch.rs / unified_exec / current_time
│       ├── mcp_resource / multi_agents / extension_tools
│       └── dynamic.rs / get_context_remaining
├── guardian/            安全守卫（敏感操作拦截）
├── exec_policy/         命令执行策略
├── realtime_conversation/  实时对话
├── tasks/ / state/ / context/ / context_manager/
└── plugins/             运行时插件
```

## 1.3 会话数据流（一图流）

```
用户输入 ──▶ input_queue（排队）
              │
              ▼
        Session.submit(op) ──▶ 后台循环（spawn 时启动）
              │                   │ 1. 组装 context（AGENTS.md + 历史 + 上下文窗口）
              │                   ▼
              │            model-provider 调用（stream）
              │                   │ 2. 返回 tool_calls
              │                   ▼
              │            tools/router → 分发 ──▶ parallel 并行执行
              │                   │        │
              │                   │        ├─ sandboxing 沙箱
              │                   │        ├─ approvals 审批
              │                   │        └─ 结果回填（executed_tool_calls）
              │                   ▼
              │            判断：还有工具调用？循环 / 结束
              ▼
        next_event() ◀── 事件总线（UI/CLI 消费）
```

## 1.4 关键设计决策（自测谈资）

1. **沙箱三件套**：`linux-sandbox`（bwrap 用户态）、`windows-sandbox-rs`、通用 `sandboxing` crate——"agent 如何安全执行命令"的标准答案
2. **审批流**：`approvals.rs`——工具按危险等级分类（读/写/执行/网络），阈值外需用户批准
3. **持久化回放**：`rollout_reconstruction.rs`（81KB）——把会话序列化存档，可断点恢复
4. **压缩有 fallback**：`compact_model_fallback.rs`——上下文压缩失败/超预算时换便宜模型
5. **MCP 全栈自研**：`codex-mcp`（作为 MCP server）、`rmcp-client`（作为 MCP client）、`mcp-server`
6. **多 agent 角色**：`agent/role.rs` + `control.rs`——主 agent 可派生子 agent（subagent）并转场

---

# 二、deepseek-ai/deepseek-harness —— "一切皆插件"的 TS monorepo

## 2.1 概览

| 项 | 值 |
|---|---|
| 语言/构建 | TypeScript + pnpm workspace；另有 `python/`、`native/` 目录 |
| 规模 | 60+ packages（`packages/`）+ 2 apps（`apps/cli`、`apps/web`） |
| 架构风格 | **cordis（koishi 系）插件框架**：dispatch waterfall/serial + ctx.effect |
| 口号 | "Everything is a Plugin" |

## 2.2 核心包（packages/core）

```
packages/core
├── agent-loop/           主循环（turn/step 状态机）
│   └── src/
│       ├── agent.ts      21KB  Agent 类：turn()/step()/preStep()/kick()
│       ├── index.ts      30KB  AgentLoop 容器（cordis service）
│       ├── tool-calls.ts 11KB  工具调用解析与回填
│       ├── runtime-context.ts / invariant.ts
├── agent/                agent 基础类型
├── agent-default-model/  默认模型解析
├── tools/                工具 schema（无运行时实现）
│   └── src/{schema, json-schema, ptc, py-types, ts-types, presentation, execution-mode}.ts
├── system-prompt/        系统提示词组装（tool-order 排序策略）
├── session/              Agent 会话容器
└── scope/                作用域（上下文范围管理）
```

**agent-loop 的核心（与 pi/codex 最大差异）**：
```ts
// agent.ts 精简逻辑
private async turn(): Promise<boolean> {
  while (true) {                                  // 一个 turn 内的 step 循环
    const decision = await this.preStep(target, { turn, step });
    // preStep →
    //   inbox.claim()                          从 Inbox 领取消息
    //   systemPrompt.assemble()                组装系统提示词
    //   dispatch.waterfall("agent/pre-step", …) ★插件可在调模型前拦截/改写
    this.session.append("step/start", { turn, step });   // 全部操作落日志
    const stepEnd = await this.step(...);        // 一次 模型调用+工具执行
    this.session.append("step/end", { turn, step });
    if (turnEnds && inbox 空) break;
  }
}
// 驱动层：while (await this.turn()) {}   直到 turn 返回 false
```

## 2.3 能力包分类（60+ 包，按职责分组）

| 分组 | packages | 说明 |
|---|---|---|
| **循环/会话** | core/agent-loop、core/session、session/*（96 文件） | turn/step 状态机；session-persistence-jsonl/sqlite、projection、stats、telemetry-otel、title-llm |
| **LLM** | llm/llm、llm-deepseek、**llm-pi-ai**、llm-retry、token-meter | 模型无关：可接 deepseek / pi 协议；带重试与 token 计量 |
| **上下文压缩** | compaction/*（31 文件） | command-compact、compaction-basic、**compaction-tool-result-pruner**（工具结果裁剪） |
| **工具** | core/tools、skill/*（13）、mcp/mcp-client | schema 先验；技能（skill）也是一种工具 |
| **多 agent** | subagent/*（114 文件，最庞大） | subagent-in-process-driver、fork-in-process、dsh-sdk、**subagent-claude-code、subagent-codex**（可兼容 Claude Code/Codex 的子代理协议！）、tool-subagent* |
| **规划** | plan/plan-mode、goal/*（27） | 目标分解（goal-round-driver）+ plan 模式 |
| **沙箱** | sandbox/*（48） | sandbox-local、sandbox-policy、**sandbox-windows-acl** |
| **插件框架** | extensions/*（58） | **cordis-host-runner、cordis-client-runner、tool-cordis、ui-cordis** |
| **钩子** | hooks/*（35） | hook-protocol、**hooks-claude-code、hooks-codex**（复用别家的 hooks 格式） |
| **应用** | apps/cli、apps/web | CLI 入口 + Web 前端 |
| **其他** | workflow、webhook、todo、terminal、subprocess、shell、storage、identity、credentials、guard、acp、api、client、bundle、boot、jobs、preset、schedule、lsp、feedback… | 全套工程支撑 |

## 2.4 独有设计（自测亮点）

1. **插件钩子贯穿循环**：`dispatch.waterfall("agent/pre-step")`——安全审查、消息改写都是插件，改循环不改核心
2. **subagent 协议兼容层**：能直接当 Claude Code / codex 的子代理跑（subagent-claude-code / subagent-codex）
3. **hooks 双向兼容**：自己的 hooks 协议之外，还能消费 claude/codex 的 hooks JSON
4. **严格 schema 工具系统**：tools 包对 Python/TS 参数做类型推导（ptc.ts、py-types.ts）
5. **工程基建完备**：knip（死代码）、oxlint、lefthook、pytest（还有 Python 测试）、.gitlab-ci

---

# 三、earendil-works/pi —— 轻量全能（TUI+Server+SDK 一体化）

## 3.1 概览

| 项 | 值 |
|---|---|
| 语言/构建 | TypeScript + npm workspaces（10 packages） |
| 规模 | 精简 monorepo，可整包读懂 |
| 架构风格 | 事件流（EventStream）+ 双层循环 + AI 层全 provider |
| 形态 | CLI（`packages/coding-agent`）+ TUI + Server + SDK（`@earendil-works/pi`） |

## 3.2 包结构

```
packages
├── agent/            Agent 引擎（核心）
│   └── src/
│       ├── agent-loop.ts     22KB  双层循环（steering 消息 + 工具调用）
│       ├── agent.ts          18KB  Agent 门面：run/continue
│       ├── harness/                Harness（行为封装）
│       │   ├── agent-harness.ts    主 Harness
│       │   ├── system-prompt.ts    系统提示词组装
│       │   ├── prompt-templates.ts 提示词模板
│       │   ├── skills.ts / reducer.ts / events.ts / messages.ts
│       │   ├── compaction/         上下文压缩（branch-summarization）
│       │   ├── session/            会话状态（session.ts、state.ts、memory.ts、jsonl codec）
│       │   └── tools/              内置工具
│       │       ├── bash.ts / read.ts / write.ts / edit.ts / edit-diff.ts
│       │       ├── image.ts / file-mutation-queue.ts / tool-context.ts
│       ├── search/           仓库扫描/搜索
│       └── proxy.ts / types.ts
├── ai/               AI 层（provider 大全，约 200+ 文件）
│   ├── providers/    40+ provider：openai/anthropic/google/deepseek/qwen/
│   │                 kimi-coding/moonshot/minimax/together/xai/zai/opencode/
│   │                 azure/bedrock/vertex/cloudflare/cerebras…（各有 .models.ts 生成清单）
│   ├── api/          协议实现：anthropic-messages、openai-responses、
│   │                 pi-messages、google-generative-ai、azure-openai-responses、
│   │                 bedrock-converse、mistral、constrained-sampling…
│   ├── auth/         OAuth 全家（anthropic/openai-codex/github-copilot/kimi/openrouter/xai
│   │                 device-code、pkce）+ credential-store
│   └── utils/        retry、provider-retry、event-stream、overflow、deferred-tools…
├── protocol/         协议与类型定义
├── client/ + server/  RPC 客户端/服务端（session 服务化）
├── coding-agent/     编码代理 CLI（read/bash/edit/write 工具的 CLI 编排）
├── tui/              终端 UI（文本界面，主题/扩展挂载点）
├── evals/            ★自带的评测套件（和你的评测集同思路）
├── session-backends/ 多个会话后端
└── telemetry/        遥测
```

## 3.3 主循环（agent-loop.ts，约 250 行）

```ts
async function runLoop(...) {
  let pendingMessages = (await config.getSteeringMessages?.()) || [];  // 用户中途输入
  while (true) {                       // 外层：允许"续跑"
    let hasMoreToolCalls = true;
    while (hasMoreToolCalls || pendingMessages.length > 0) {   // 内层：工具循环
      // 先注入 pending 消息（steering）
      // 流式调用模型 streamAssistantResponse(...)
      // 若 stopReason === "error" | "aborted" → 兜底
      // 有 tool_calls → 执行并回填 → hasMoreToolCalls=true
      // nextTurn 可切换 model/reasoning（prepareNextTurn）
    }
    if (!等待续跑) break;
  }
}
```

## 3.4 独有设计

1. **模型无关做到极致**：`providers/` 40+ 家 + `api/` 多协议 + OAuth 全家（含 GitHub Copilot、OpenAI Codex 登录）——AI 层和引擎层彻底解耦，是我们 mini_agent ChatClient 思路的生产级放大版
2. **自带 evals 包**：评测是一等公民（对应我们的评测集）
3. **会话 JSONL 持久化**：`harness/session/jsonl/`（codec/repo/storage）——会话可存档恢复
4. **扩展系统**：themes/skills/extensions（见 npm 包 examples/），TUI 级深度定制
5. **工具文件操作工程化**：`file-mutation-queue`（文件写操作排队防冲突）、`edit-diff`（diff 式编辑省 token）

---

# 四、anthropics/claude-code —— 提示词生态（核心闭源）

## 4.1 概览

| 项 | 值 |
|---|---|
| 仓库内容 | 核心循环**闭源**；开源 = 插件/命令/示例/变更日志 |
| 规模 | 229 文件；CHANGELOG.md 5300 行（v2.1.251） |
| 可学习点 | 插件机制、allowed-tools 声明、多 agent 提示词剧本、hooks 示例 |

## 4.2 组成结构

```
claude-code/
├── plugins/                插件（15 个）
│   ├── code-review/        多 agent 代码评审
│   ├── feature-dev/        功能开发流程
│   ├── frontend-design/    前端设计
│   ├── commit-commands/    提交命令
│   ├── security-guidance/  安全指导
│   ├── hookify/ / plugin-dev/ / agent-sdk-dev/
│   ├── claude-opus-4-5-migration/ / pr-review-toolkit/
│   ├── explanatory-output-style/ / learning-output-style/
│   └── ralph-wiggum/       整活
│   └── 每个插件结构：
│       ├── .claude-plugin/plugin.json   （name/description/author）
│       └── commands/*.md                （带 YAML 前言的提示词剧本）
├── .claude/commands/       内置命令（commit-push-pr / dedupe / triage-issue）
├── examples/
│   ├── hooks/bash_command_validator_example.py   （bash 命令校验钩子示例）
│   ├── gateway/、mdm/、settings/
└── CHANGELOG.md            5300 行演进记录（hook 事件/权限模型变化）
```

## 4.3 插件的"提示词即软件"模式

```markdown
# plugins/code-review/commands/（某命令，精简）
---
allowed-tools: Bash(gh issue view:*), Bash(gh pr view:*), mcp__github_inline_comment__*
description: Code review a pull request
---
1. Launch a haiku agent：检查 PR 是否可评审（closed/draft/已评论）
2. Launch a haiku agent：收集相关 CLAUDE.md
3. Launch a sonnet agent：读 diff 摘要
4. Launch 4 agents in parallel：独立评审，返回 issues
...

# 插件清单（manifest）
{ "name": "code-review",
  "description": "Automated code review for pull requests using multiple
                  specialized agents with confidence-based scoring",
  "version": "1.0.0", "author": { "name": "Boris Cherny", ... } }
```

**三个机制**：
1. **allowed-tools 白名单**：命令声明可用的工具子集（`Bash(gh *:*)` 前缀匹配）——权限最小化
2. **多 agent 编排**：haiku（省 token 的轻活）/ sonnet（重活）/ parallel 并行——成本分层
3. **hooks**：事件挂钩（如 bash 命令执行前校验），`examples/hooks` 有 Python 示例

## 4.4 学习价值（自测怎么用）

- 它是"**当前提示词工程的天花板公开样本**"：工具白名单写法、agent 成本分层、可重复剧本
- 自测被问"如何设计 Agent 权限"→ 答 allowed-tools 前缀匹配分级
- 自测被问"多 agent 怎么分工"→ 答 claude 的 haiku/sonnet 成本分层 + 并行评审

---

# 五、四者横向总表

| 维度 | codex | deepseek-harness | pi | claude-code |
|---|---|---|---|---|
| 语言 | Rust | TypeScript | TypeScript | Markdown |
| 循环模型 | 事件驱动 Session + InputQueue | turn/step 状态机 + Inbox + 插件钩子 | 双层 while + 事件流 | 提示词剧本（核心闭源） |
| 工具系统 | registry/router/parallel/orchestrator + 审批 + 沙箱 | tools(schema) + skill + mcp + 插件拦截 | harness/tools（bash/read/write/edit + 队列） | allowed-tools 白名单 |
| 上下文 | compact + fallback + context_window + AGENTS.md | compaction 4 包 + projection | compaction（branch-summarization）+ JSONL 会话 | CLAUDE.md 约定（闭源） |
| 多 agent | agent/control + role + subagent | subagent 11 子包（含兼容 claude/codex）| harness 内单 agent + 扩展 | 插件内多 agent 剧本 |
| 沙箱 | 3 套（linux/windows/generic）| sandbox 4 包（含 windows-acl）| 无（本地进程） | 闭源 |
| 评测 | 大规模 _tests.rs | vitest 全包 + pytest | ★packages/evals | 无 |
| 读源码难度 | 极高 | 中 | 低（建议从这入门） | 读提示词 |

## 与我们的 mini_agent（resume-matcher）对照

| 我们的模块 | 对应生产级答案 |
|---|---|
| `tools.py` 签名→schema | codex tools/registry、deepseek core/tools（类型推导更全） |
| `agent.py` while 循环 | pi runLoop / deepseek turn+step / codex session 事件泵 |
| `memory.py` 窗口截断 | codex compact+fallback、deepseek compaction-pruner、pi branch-summarization |
| `mcp.py` 从零实现 | codex mcp_runtime、deepseek mcp-client、pi 无内置（走协议层） |
| `eval/` 评测集 | pi packages/evals（同思路！） |

**生产级共有的、我们还没有的**：审批流、沙箱、并行工具、会话持久化恢复、steering 消息（用户中途打断）、多 agent。

> 学习路线建议：先读 pi（agent-loop.ts 共 300 行内看懂循环）→ 再读 deepseek agent-loop（看插件钩子）→ 最后挑 codex 的 approvals/sandboxing/compact 单模块精读。claude-code 用于提示词写作参考。