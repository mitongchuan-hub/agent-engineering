# Coding Agent Python 教学重建

本仓库用于分别构建四套 Coding Agent 的 Python 教学项目。每套课程以对应 GitHub 源码和可验证运行行为为依据，沿该项目自己的启动、运行和退出链路逐章重建，不共享统一的 Mini Agent 内核，也不把四家的机制混成一套公共实现。

## 学习对象

| 项目 | 源码仓库 | 本地源码 | 证据边界 |
| --- | --- | --- | --- |
| Pi（当前安装版本） | `earendil-works/pi` | `agent-source/pi/` | 完整 TypeScript 源码 |
| DeepSeek Harness | `deepseek-ai/DeepSeek-Harness` | `agent-source/deepseek-harness/` | 完整 TypeScript/Cordis 源码 |
| Codex | `openai/codex` | `agent-source/codex/` | 完整 Rust 核心源码 |
| Claude Code | `anthropics/claude-code` | `agent-source/claude-code/` | 官方公开插件、Agent、Skill、Hook、Command、MCP 与配置；不含闭源核心执行引擎 |

四个源码目录都是独立 Git 仓库，并被本仓库的 `.gitignore` 排除。它们用于源码核查、原生测试和运行验证，不会作为教学代码直接提交到本仓库。

## 计划产物

```text
learn-pi/
learn-deepseek-harness/
learn-codex/
learn-claude-code/
```

每套课程都是独立 Python 工程，按内容拆分为 `s01` 到最终综合章。每章提供中文 README、可独立运行的 `code.py`、架构图、源码定位和离线测试；整套课程提供综合实现、真实模型可选接入、CI 与 Web 阅读界面。

## 实现原则

1. 四家分别建模，不依赖共同的 Agent 基类、工具注册器或会话实现。
2. 章节顺序来自该项目的真实调用链，不使用跨项目的公共概念顺序。
3. 教学实现统一使用 Python，但类名、状态、事件和生命周期尽量保留原项目语义。
4. 每项结论记录上游源码路径和固定提交；Python 简化点必须明确标注，不能冒充原始实现。
5. 每章默认可用 Mock 离线运行，配置凭据后可选调用真实模型。
6. Claude Code 严格区分公开源码、公开文档和黑盒运行观察，不把不可见的核心循环写成源码事实。

## 实施顺序

1. Pi
2. DeepSeek Harness
3. Codex
4. Claude Code

顺序只用于安排建设进度，四套课程的代码、术语、测试和文档保持独立。源码位置、固定版本和重新获取命令见 [`agent-source/README.md`](agent-source/README.md)。
