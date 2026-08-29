# DEEP DIVE: deepseek-ai/deepseek-harness（TypeScript）

> 源码：`agent-source/deepseek-harness/` ｜ 语言：TypeScript（pnpm monorepo，60+ 包）
> 定位：DeepSeek 官方 Agent，"Everything is a Plugin" 的极客作品
> 阅读难度：★★★★（包多，但单个包都不大，可局部精读）

## 一、定位

deepseek-harness 最大的看点：**把 Agent 的每个能力都做成插件**。
基于 cordis（koishi 系）插件框架，循环本身的 turn/step 状态机 + Inbox 消息领取
都暴露给插件层拦截改写。读它 = 学"可插拔 Agent 架构"。

## 二、代码地图（按学习顺序）

| 顺序 | 包/文件 | 内容 | 优先级 |
|---|---|---|---|
| 1 | `packages/core/agent-loop/src/agent.ts` | turn/step 状态机核心（21KB） | ⭐ 必读 |
| 2 | `packages/core/agent-loop/src/index.ts` | AgentLoop 容器（cordis service，30KB） | ⭐ |
| 3 | `packages/core/agent-loop/src/tool-calls.ts` | 工具调用解析与回填（11KB） | ⭐ |
| 4 | `packages/core/system-prompt/` | 系统提示词组装 + **tool-order 排序策略** | 🔍 |
| 5 | `packages/core/tools/` | 工具 schema（json-schema/ptc/py-types/ts-types） | 🔍 |
| 6 | `packages/subagent/subagent-*` | 11 个子包的多 agent 体系 | ⭐（最有含金量） |
| 7 | `packages/hooks/hooks-claude-code` `hooks-codex` | **兼容别家 hooks 格式** | 📖 |
| 8 | `packages/compaction/*` | 压缩（含 tool-result-pruner） | 🔍 |
| 9 | `packages/llm/llm-deepseek` `llm-pi-ai` | 模型适配（居然也支持 pi 协议） | 📖 |

## 三、核心机制拆解

### ① 循环 = turn/step 状态机（agent.ts）

```ts
private async turn(): Promise<boolean> {
  while (true) {
    const decision = await this.preStep(target, { turn, step });
    //   inbox.claim() —— 从 Inbox 领取消息（支持并发唤醒）
    //   systemPrompt.assemble() —— 组装上下文
    //   ★ dispatch.waterfall("agent/pre-step", ...) —— 插件拦截点
    this.session.append("step/start", { turn, step });
    const stepEnd = await this.step(...);
    this.session.append("step/end", { turn, step });
    if (turnEnds && this.inbox.nextStep.length === 0) break;
  }
}
```
对比：pi 是"双层 while"（直观），deepseek 是"显式状态机"（可插拔）。两种哲学。

### ② 插件钩子：水流式改写（waterfall）

```
插件链（按注册顺序）：
  pluginA(pre-step) → pluginB(pre-step) → 默认 enter 决策
每个插件可以把 decision 改成 "reject"（阻断）或改写 messages
```
**安全审查、参数修正、多租户隔离都可以是插件**——改能力不动核心循环。
这正是"Everything is a Plugin"的实现内核。

### ③ subagent 兼容层（最独特的资产）

`packages/subagent/` 11 个子包，包括：
- `subagent-in-process-driver`：进程内子代理（快）
- `subagent-fork-in-process`：fork 隔离（稳）
- `subagent-claude-code` / `subagent-codex`：**直接借用 Claude Code / codex 的子代理协议**
- `tool-subagent`（发起）/ `tool-subagent-control`（控制）/ `tool-subagent-report`（汇报）

含义：别人家的 Agent 可以当我们的子代理，反之亦然——互操作做到协议层。

### ④ hooks 双向兼容

`packages/hooks/`：自己的 hook-protocol 之外，还有 `hooks-claude-code`、`hooks-codex`
桥接包（bridge.spec 测试覆盖）——复用生态既有的 hooks 格式，降低迁移成本。

## 四、三档阅读路线

- **30 分钟**：`agent-loop/src/agent.ts` 的 turn()/step()，看懂状态机 + 插件钩子
- **半天**：agent-loop 三件套 + system-prompt 包（tool-order 测试），理解"上下文怎么组装"
- **3 周**：subagent 体系 + hooks 桥接 + compaction，画一张"插件如何挂进循环"的图

## 五、知识要点

1. "Agent 的循环有哪几种实现？" → pi 双层 while / deepseek 状态机 / codex 事件泵，各说一句差异
2. "怎么给 Agent 加安全审查？" → hook 钩子（deepseek waterfal）/ partner（codex approvals），两种答案都要会
3. "多 Agent 怎么做？" → subagent 协议兼容层（deepseek）/ agent role+control（codex）
4. "工具参数怎么强类型？" → deepseek tools 包有 ptc.py-types/ts-types 推导

## 六、动手练习

1. 搜 `dispatch.waterfall(` 出现的位置，列出全部插桩点（不止 pre-step）
2. 读 `subagent-claude-code` 的桥接实现，说清它怎么"翻译"两边的协议
3. 跑一下 `packages/core/agent-loop/tests`（vitest），观察状态机测试怎么写