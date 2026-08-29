# 🤖 Learn Mini Agent —— 从 0 到 1 手写 Agent 框架（秋招向）

> 借鉴 [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 的"分步演进 + 每步可运行 + 教学文档"形态，
> 从零构建一个**通用 Agent 框架**，并在其上实现**简历×JD 匹配应用**，再逐步加上**评测**与 **MCP 协议**。

## 为什么值得看

面试 Agent 岗位被问"你写过 Agent 吗"？与其说"我调过 LangGraph"，不如说：
**"我从一个 while 循环开始，逐步手写了工具注册、上下文管理、LLM 客户端、评测集和 MCP 协议。"**

每一章都是独立的可运行代码 + 面试问答。全部代码无需 API Key 也能演示（内置演示模型），配 Key 后走真实大模型。

## 学习路径（s01 → s10）

| 步骤 | 主题 | 一句话 | 对应面试题 |
|---|---|---|---|
| [s01](s01_agent_loop/) | Agent Loop | 一个 `while` 循环就是 Agent 的心脏 | Agent 主循环怎么写？ |
| [s02](s02_tool_registry/) | 工具注册 | 函数签名自动生成 JSON Schema | Function Calling 协议是什么？ |
| [s03](s03_llm_client/) | LLM 客户端 | OpenAI 兼容协议，模型无关 | 怎么让 Agent 不绑定 GPT/DeepSeek？ |
| [s04](s04_context_memory/) | 上下文管理 | 字符预算窗口截断，不拆散工具问答对 | Context 无限膨胀怎么办？ |
| [s05](s05_resume_matcher/) | 规则工具 + LLM 混合 | 可计算的交给规则，可推理的交给 LLM | Agent 应用怎么做？规则 vs LLM 怎么分工？ |
| [s06](s06_evaluation/) | 评测集 | Oracle 用例回归 + 单测 | 你怎么量化 Agent 效果？ |
| [s07](s07_mcp_server/) | MCP 协议 | 从零实现 JSON-RPC 生命周期 | 什么是 MCP？和 function calling 区别？ |
| [s08](s08_mcp_agent_bridge/) | MCP × Agent | Agent 动态连接外部 MCP 服务器 | 你的 Agent 怎么接入外部工具生态？ |
| [s09](s09_error_recovery/) | 健壮性 | 参数兜底、错误自愈、迭代上限 | 工具调用失败怎么办？死循环怎么防？ |
| [s10](s10_comprehensive/) | 综合成品 | 完整 resume-matcher 全量 | 完整项目演示 |

## 快速开始

```bash
cd learn-mini-agent

# ① 无需 Key 的演示模式（默认，内置演示模型）
python s01_agent_loop/code.py

# ② 配 Key 走真实模型：复制 .env.example 为 .env 并填 Key
#    支持任意 OpenAI 兼容服务：DeepSeek / OpenAI / 智谱 / Moonshot ...
```

## 代码哲学

1. **每步一个可运行文件**：`sXX/code.py`，直接 `python` 跑
2. **零框架依赖**：核心不依赖 LangChain/LangGraph，全手写
3. **演示模式优先**：没 Key 也能看到完整行为
4. **README 即笔记**：每步含「问题→方案→原理→运行→练习→面试问答」

## 面试价值速查

| 简历写法（推荐） | 对应章节 |
|---|---|
| 手写 Agent 框架：ReAct 循环、工具 schema 自动生成、上下文预算 | s01 s02 s04 |
| 规则打分 + LLM 推理混合架构，可审计可复现 | s05 |
| 评测集 + 15 个单测，结论准确率 100% | s06 |
| 从零实现 MCP 协议（JSON-RPC + stdio），Agent 动态外接 | s07 s08 |
| 生产级健壮性：错误回传自愈、参数类型兜底 | s09 |