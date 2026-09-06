# 上游源码工作区

此目录只存放四个上游项目的本地检出，以及后续课程所依据的源码证据。旧版 Mini Agent、零散 Python 机制示例、横向比较表和示例应用已移除。

## 当前快照

| 项目 | 上游 | 分支 | 当前提交 | 本地目录 |
| --- | --- | --- | --- | --- |
| Pi | `https://github.com/earendil-works/pi.git` | `main` | `9767ba2` | `pi/` |
| DeepSeek Harness | `https://github.com/deepseek-ai/DeepSeek-Harness.git` | `master` | `d347e70` | `deepseek-harness/` |
| Codex | `https://github.com/openai/codex.git` | `main` | `6af3454` | `codex/` |
| Claude Code | `https://github.com/anthropics/claude-code.git` | `main` | `ab9b2cf` | `claude-code/` |

这些是浅克隆：当前提交的源码树完整，仅未下载更早的 Git 历史。需要研究版本演进时，在对应目录执行 `git fetch --unshallow`。

这些源码仓库用于确定各项目的真实结构和行为。顶层后续建立的 `learn-pi/`、`learn-deepseek-harness/`、`learn-codex/` 与 `learn-claude-code/` 将分别使用 Python 重建教学版本；四套课程不会共享统一 Agent 运行时。原生构建与测试仍用于核验 Python 教学实现没有误读上游。

## 独立入口

### Pi

从 `pi/packages/coding-agent/src/cli.ts` 进入，先完成 Coding Agent 的参数、配置、资源和 Session 启动链，再进入 `packages/agent` 的 Agent 与循环，最后追到 `packages/ai` 的模型 Provider 和流式协议。所有运行与测试使用仓库自己的 Node.js/pnpm 工具链。

### DeepSeek Harness

从 `deepseek-harness/apps/cli/src/bin.ts` 进入，沿 CLI Profile Boot、Cordis Context/Service、插件装配进入 `packages/core/agent-loop/src/agent.ts`，再分别追踪工具、上下文管理、模型、沙箱、Subagent 和终止流程。以仓库的架构文档和 TypeScript 测试校验调用链。

### Codex

从 `codex/codex-rs/cli/src/main.rs` 进入，分别跟踪交互式 TUI、非交互 Exec 和其他子命令如何进入 `codex-core`。随后按 Rust 类型与事件流追踪 Thread/Turn、模型客户端、工具路由、审批、沙箱、Rollout 持久化、压缩和关闭过程。

### Claude Code

从 `claude-code/plugins/README.md` 和各官方插件清单进入，分别学习 Commands、Agents、Skills、Hooks、MCP、权限和插件生命周期。官方仓库没有 Claude Code 核心 Agent Loop，因此核心运行行为只能通过公开文档、SDK 与受控实验验证，不能标记为源码精读结果。

## 重新获取

在仓库根目录执行：

```powershell
git clone --depth 1 https://github.com/earendil-works/pi.git agent-source/pi
git clone --depth 1 https://github.com/deepseek-ai/DeepSeek-Harness.git agent-source/deepseek-harness
git clone --depth 1 https://github.com/openai/codex.git agent-source/codex
git clone --depth 1 https://github.com/anthropics/claude-code.git agent-source/claude-code
```

查看本地是否仍处于记录的快照：

```powershell
git -C agent-source/pi rev-parse --short HEAD
git -C agent-source/deepseek-harness rev-parse --short HEAD
git -C agent-source/codex rev-parse --short HEAD
git -C agent-source/claude-code rev-parse --short HEAD
```

更新某个项目时只在它自己的目录执行 `git pull --ff-only`，并同步更新本页记录的提交。不要把四个项目合并成一套本地 Agent 实现。
