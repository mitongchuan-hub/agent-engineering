# DEEP DIVE: anthropics/claude-code（提示词生态）

> 源码：`agent-source/claude-code/` ｜ 形态：**核心闭源**，开源的是插件/命令/skills/钩子示例
> 定位：Claude Code 的"配方"，**提示词工程的公开天花板**
> 阅读难度：★（代码少，全是 Markdown，但价值极高）

## 一、定位

claude-code 仓库没有引擎源码——但它是**最值得抄的提示词/工作流设计样本**。
它教会我们：Agent 的能力上限，一半在代码，一半在**剧本**（命令/插件）。
面试被问"怎么设计 Agent 行为"，答案就在这些 md 里。

## 二、代码地图

| 路径 | 内容 | 优先级 |
|---|---|---|
| `plugins/code-review/` | 多 agent 代码评审插件（最完整样例） | ⭐ 全文精读 |
| `plugins/feature-dev/` | 功能开发流程插件 | 🔍 |
| `plugins/frontend-design/` | 前端设计插件 | 📖 |
| `plugins/security-guidance/` | 安全引导插件 | 📖 |
| `.claude/commands/` | 内置命令（commit-push-pr/dedupe/triage-issue） | 🔍 |
| `examples/hooks/` | bash 命令校验钩子（Python 示例） | 🔍 |
| `CHANGELOG.md` | 5300 行演进史（hook 事件/权限模型变化） | 📖 按需查 |

## 三、核心机制拆解

### ① 插件 = manifest + 剧本（两件套）

```
plugins/code-review/
├── .claude-plugin/plugin.json   ← 元数据（name/description/author）
└── commands/*.md                ← 剧本（YAML 头部 + 正文指令）
```
一个插件可以带多个命令；一个命令是一个完整的"工作流剧本"。

### ② allowed-tools：声明式权限白名单（最值得抄的）

```markdown
---
allowed-tools: Bash(gh issue view:*), Bash(gh search:*), Bash(gh pr view:*),
               mcp__github_inline_comment__create_inline_comment
---
```
- `Bash(gh pr view:*)`：允许执行 `gh pr view <任意参数>` 系命令
- `mcp__github_inline_comment__*`：允许调用特定 MCP 服务器上的特定工具
- 凡是不在白名单里的，模型不能用——**权限最小化**的直接落地

### ③ 多 agent 编排 = 成本分层（亮点）

code-review 命令的正文：
```markdown
1. Launch a haiku agent：检查 PR 是否可评审（廉价预检）
2. Launch a sonnet agent：读 PR diff 摘要
3. Launch 4 agents in parallel：独立评审，各自返回 issues
```
关键设计：
- **haiku 干轻活**（预检/读 CLAUDE.md），**sonnet 干重活**——成本分层
- **并行评审**：4 个 agent 独立看同一 PR，再汇总——减少单点盲区
- 指令精确到工具策略："All tools are functional... Do not test tools"（省探索调用）

### ④ hooks：事件注入

`examples/hooks/` 提供 bash 命令执行前校验的钩子（Python 实现）：
在命令真正执行前拦一道，不合法就拦截——和 codex 的 permission hooks 同思想。

## 四、阅读路线

- **20 分钟**：读 `plugins/code-review/commands/` 的一个命令 + plugin.json，看懂"剧本=软件"
- **1 小时**：把所有 15 个插件的 description 扫一遍，看 Anthropic 官方把能力边界设计在哪
- **半天**：抄 3 个命令的精髓，给我们的 resume-matcher 写一个"招聘评估"命令剧本

## 五、面试考点

1. "怎么给 Agent 限制工具权限？" → allowed-tools 前缀匹配白名单（claude）/ 审批流（codex）
2. "多 Agent 怎么降本？" → 便宜模型干预检、贵模型干重活、可并行就并行
3. "Agent 的'提示词'和'代码'怎么分工？" → 可变的逻辑进提示词（剧本），不可变的进代码（循环/安全）
4. "为什么 Claude Code 核心不开源？" → 它的护城河一部分就是这套极致的提示词编排

## 六、动手练习

1. 给我们的 s05 写一个"JD 匹配评估"命令剧本（含 allowed-tools 头），体验声明式权限
2. 对比 code-review 和 deepseek-harness 的 subagent：协议兼容 vs 提示词编排，两种做法
3. 翻 CHANGELOG 找一次"hook 事件增加"的记录，还原它为什么要加这个事件