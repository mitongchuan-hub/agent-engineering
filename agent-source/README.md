# Agent 源码精读系列（秋招向）

> 4 大 Coding Agent 源码（真实 GitHub 克隆）的精读导览 + 结构对比 + 动手路线。
> 与 [learn-mini-agent](../learn-mini-agent/)（手写教程）互补：**那边教原理，这边看天花板**。

## 📂 本目录内容

```
agent-source/
├── codex/                        # openai/codex（Rust，100+ crates）
├── deepseek-harness/             # deepseek-ai/deepseek-harness（TS，60+ 包）
├── pi/                           # earendil-works/pi（TS，10 包）
├── claude-code/                  # anthropics/claude-code（提示词生态）
│
├── README.md                     # ← 本索引
├── CODING_AGENTS_STRUCTURE.md    # 四者核心循环/工具/上下文 横向对比总表
│
├── deepdive-codex.md             # codex 精读：代码地图+机制拆解+路线+考点
├── deepdive-deepseek-harness.md  # deepseek 精读：状态机+插件钩子+subagent
├── deepdive-pi.md                # pi 精读：事件流+并行工具+40 家 provider
└── deepdive-claude-code.md       # claude 精读：allowed-tools+多 agent 剧本

# —— 三家的分步教学（learn-claude-code 格式，Python 可运行） ——
codex_learn/       c01~c07：codex 核心机制教学（Bash 工具/并行/审批/沙箱/压缩/持久化/多 agent）
deepseek_learn/    d01~d07：deepseek 核心机制教学（状态机/插件钩子/Inbox/严格 schema/子代理/裁剪/提示词组装）
pi_learn/          p01~p07：pi 核心机制教学（事件流/steering/并行/失败进流/provider 层/压缩/JSONL）
```

## 🗺️ 阅读路径（三条线任选）

**A. 从易到难（推荐）**：`deepdive-pi.md`（事件流/并行工具体验好）
→ `deepdive-deepseek-harness.md`（插件化架构）→ `deepdive-codex.md`（工程外壳）→ `deepdive-claude-code.md`（提示词) 

**B. 按主题横切**：主循环（四家对比见 CODING_AGENTS_STRUCTURE.md 第 1 节）
→ 上下文（codex compact / deepseek compaction / pi branch-summarization）
→ 工具体系（codex approvals+parallel / deepseek tools+schema / claude allowed-tools）

**C. 面试突击（每份读"面试考点"一节即可）**：约 40 分钟过完 4 份考点清单

## ⭐ 分步教学（推荐：看懂机制，动手跑）

| 教学项目 | 几步 | 你将亲手重建 | 入口 |
|---|---|---|---|
| **codex_learn** | c01~c07 | Bash 工具→并行执行→审批流→沙箱→上下文压缩→会话持久化→多 Agent | [入口](codex_learn/README.md) |
| **deepseek_learn** | d01~d07 | 状态机循环→插件钩子→Inbox→严格 schema→子代理→结果裁剪→提示词组装 | [入口](deepseek_learn/README.md) |
| **pi_learn** | p01~p07 | 事件流→steering→并行工具→失败进流→provider 层→分支压缩→JSONL 会话 | [入口](pi_learn/README.md) |

## 💡 一句话速查（面试急救）

| 被问 | 答案（可引用） |
|---|---|
| Agent 循环有几种？ | 双层 while（pi）/ turn+step 状态机（deepseek）/ 事件泵 Session（codex）/ 提示词剧本（claude） |
| 模型调用失败怎么办？ | pi 把失败编码进流（stopReason=error）；我们 s09 用错误回传自愈 |
| 工具并行执行？ | pi 两阶段（prepare 串行→execute 并发）；codex parallel.rs 同思路 |
| 上下文膨胀？ | 窗口截断（我们 s04）→ codex 压缩 hooks + fallback（高级） |
| 怎么安全执行命令？ | codex：策略匹配+沙箱+审批流；claude：allowed-tools 白名单 |
| 多 Agent 咋做？ | codex agent/role+control；deepseek subagent 协议兼容层；claude 提示词编排 |
| 模型无关？ | pi 40+ provider，每厂商一文件；我们 s03 ChatClient 同源 |
| 效果怎么量化？ | pi 自带 packages/evals；我们 s06 评测集同思路 |

## 🔗 与手写教程的联动

看完某家源码后回 learn-mini-agent 升级对应章节：

| 你在源码里学到的 | 回手写教程 |
|---|---|
| pi 的"失败进流" | 给 s09 错误处理做一次重构 |
| codex 的"审批" | 给 s09 加一道防线：危险工具需确认 |
| deepseek 的插件钩子 | 给框架加 dispatch 插桩点（s02 的 registry 扩展） |
| claude 的 allowed-tools | 给 s08 的 mcp 桥接加工具白名单 |
| codex/deepseek 的持久化 | 给 s04 的 buffer 加 JSONL 会话存档 |

## ⚠️ 前提说明

- 源码为 2026-08 GitHub 快照（浅克隆，无 git 历史；需要历史请 `git fetch --unshallow`）
- claude-code 无引擎源码（官方闭源），仓库内容是插件/命令/hooks 生态
- Star 数勿背死数，面试说量级即可