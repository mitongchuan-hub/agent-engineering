# Agent 秋招备战体系总仓库

> 从零备战 AI Agent 岗位的完整学习与实战资产（见 **[LEARNING_MAP.md](LEARNING_MAP.md)** 学习总地图）。

## 仓库内容

| 目录 | 内容 | 定位 |
|---|---|---|
| `learn-mini-agent/` | s01~s10 从零手写 Agent 框架教学 | 原理：循环/工具/上下文/MCP/评测/健壮性 |
| `agent-source/codex_learn/` | c01~c07 | codex 源码机制重建（工程外壳） |
| `agent-source/deepseek_learn/` | d01~d07 | deepseek 源码机制重建（可插拔架构） |
| `agent-source/pi_learn/` | p01~p07 | pi 源码机制重建（事件驱动） |
| `agent-source/deepdive-*.md` | 4 份源码精读导览 | codex / deepseek / pi / claude-code |
| `resume-matcher/` | 完整成品项目 | 15 单测 + 评测集 + MCP + 真实 LLM 报告 |
| `agent_projects_research.md` | 项目调研 | 秋招选型情报 |

## 快速开始

```bash
# ① 手写框架教学（无需 Key）
python learn-mini-agent/s01_agent_loop/code.py

# ② 源码机制重建（21 步全可跑）
python agent-source/codex_learn/c01_bash_tool/code.py
python agent-source/deepseek_learn/d01_turn_step_loop/code.py
python agent-source/pi_learn/p01_event_stream/code.py

# ③ 成品项目（无 Key Mock / 配 Key 真实 LLM）
python resume-matcher/run.py --mock
python resume-matcher/run.py --verbose     # 配 .env 后走真实大模型
```

> 本仓库所有教学代码无需 API Key（内置演示模型）；`.env` 密钥已排除，不提交。