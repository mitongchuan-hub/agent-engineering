# GitHub 优秀 Agent 项目调研（学习笔记）

> 调研时间：2026-xx（star 数为 GitHub API 实时查询，可能会有波动）
> 分类维度：**自测价值**（源码可读性、技术深度、话题热度）× **简历价值**

---

## 一、Agent 编排框架（必读，自测核心）

| 项目 | Star | 语言 | 一句话定位 |
|---|---|---|---|
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | ~40k | Python/JS | 用状态机/图结构编排 agent 的业界标准 |
| [microsoft/autogen](https://github.com/microsoft/autogen) | ~60k | Python | 微软出品，多智能体对话式协作（现在主线叫 AG2） |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | ~57k | Python | 角色化多智能体协作（Role/Goal/Backstory） |
| [huggingface/smolagents](https://github.com/huggingface/smolagents) | ~29k | Python | 极简 agent，CodeAgent/ActionAgent，适合读源码 |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | ~29k | Python | OpenAI 官方 SDK，Handoff 机制是亮点 |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | ~19k | Python | 类型安全 agent 框架，与 FastAPI 同作者 |
| [camel-ai/camel](https://github.com/camel-ai/camel) | ~17k | Python | 多智能体角色扮演框架的开创者 |
| [geekan/MetaGPT](https://github.com/geekan/MetaGPT) | ~90k+ | Python | "多智能体软件公司"，SOP 流程化开发 |

**自测为什么考这些**：
- LangGraph 的 `StateGraph` 节点/边/条件边如何实现状态共享 → 考验图论 + 数据结构设计
- Agent 循环的本质 = `while (有工具要调用) { LLM 生成 → 解析工具调用 → 执行 → 回填 }`，几乎所有框架都是这个 loop 的变体
- 记忆/上下文管理（token 裁剪、摘要）、工具注册与 schema 校验

---

## 二、编码 Agent（Code Agent，当下最热）

| 项目 | Star | 一句话定位 |
|---|---|---|
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | ~140k | 终端编码 agent 标杆（闭源，但 skills/系统提示词已开源） |
| [All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands)（原 OpenDevin） | ~40k+ | 最强开源自研编码 agent，适合精读 |
| **earendil-works/pi**（你正在用的这个工具） | ~98k | 全开源编码 agent，TypeScript，代码量小、易读，**强烈推荐精读** |
| [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | ~75k | "Bash is all you need"——从 0 到 1 手写一个 claude-code 式 agent harness |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | ~111k | 浏览器自动化 agent（让 agent 操作网页） |

**自测为什么考这些**：学习大厂算法/AI 岗必问"Agent 如何读写文件、如何执行命令、如何做沙箱隔离、如何断点续跑"。pi 和 learn-claude-code 都是代码量小到可以一周读完的绝佳材料。

---

## 三、Agent 平台/应用层

| 项目 | Star | 一句话定位 |
|---|---|---|
| [langgenius/dify](https://github.com/langgenius/dify) | ~153k | 国内出海最成功的 agent/RAG 工作流平台（前后端 + 编排） |
| [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | ~186k | agent 概念的引爆者 |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | ~101k | 金融交易多智能体（分析师/交易员/风控对抗） |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | ~81k | 字节开源的长任务 SuperAgent（研究+写码+创作，沙箱化） |
| [ComposioHQ/composio](https://github.com/ComposioHQ/composio) | ~29k | 工具/集成层（Agent 连接 250+ 应用） |

---

## 四、MCP 与工具生态（必答"你了解 MCP 吗"）

| 项目 | Star | 一句话定位 |
|---|---|---|
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | ~89k | Anthropic 官方的 MCP 官方参考 server 集合 |
| [microsoft/markitdown](https://github.com/microsoft/markitdown) | ~176k | 文档（PDF/Office/网页）→ Markdown，agent 的文件进料工具 |
| [GetZep/graphiti](https://github.com/getzep/graphiti) | ~30k | 时间感知的知识图谱记忆层 |
| [letta-ai/letta](https://github.com/letta-ai/letta) | ~24k | MemGPT，agent 的记忆管理 |

**自测必问**：MCP 是什么、和 function calling 的区别、为何是上下文工程的关键拼图。

---

## 五、学习路线（免费教程，学习速成）

| 项目 | Star | 内容 |
|---|---|---|
| [datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents) | ~75k | 《从零开始构建智能体》中文教程，从原理到实践 |
| [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | ~135k | 100+ agent/RAG 应用实例，抄作业神器 |
| [Snailclimb/JavaGuide](https://github.com/Snailclimb/JavaGuide) | ~158k | 注意：如果你是后端岗，Agent 只是加分项，基础八股仍是基本盘 |

---

## 六、学习视角的优先级建议

### 时间有限（1~2 周）
1. **精读 1 个框架源码**：推荐 `smolagents`（代码量最小、纯 Python）或 `pi`（TypeScript）
2. **读完 hello-agents 前 5 章**：把 ReAct / function calling / 工具循环讲明白
3. **手写一个 100 行的 mini-agent**（可选：参考 learn-claude-code）

### 时间充裕（1 个月）
1. 精读 LangGraph 源码（StateGraph 设计）+ 手搓一个 50 行图编排
2. 用 OpenAI Agents SDK 或 LangGraph 做一个学习笔记项目：
   - 简历解析 + 岗位 JD 匹配 agent（体现 RAG + tool-use）
   - 多智能体读者模拟器（体现多 agent 协作 + 记忆）
3. 了解 MCP + 浏览器 agent（browser-use），能说清架构即可

### 简历上怎么写（HR/AI 部门都认可）
- ✅ "基于 LangGraph 实现多智能体简历分析系统，支持 3 种工具调用与状态回滚，自测候选回复准确率提升 XX%"
- ✅ "从零实现 Mini Agent Framework：Tool 注册、ReAct 循环、上下文压缩，支持 5 类工具，代码 800 行"
- ❌ 不要只写"熟练使用 AutoGPT"——读者会追问实现细节

### 自测高频追问清单（对着自测）
1. ReAct 为什么叫 ReAct？和 Plan-and-Execute 区别？
2. Function calling 的 protocol 长什么样？如何保证参数 schema 正确？
3. 多智能体三种协作范式：单一编排（LangGraph）/角色化（CrewAI）/对话式（AutoGen）各自优缺点？
4. Agent 上下文无限膨胀怎么解决？(裁剪/摘要/向量检索/图记忆)
5. 工具调用解析失败/幻觉参数如何兜底？
6. 什么是 MCP？Server/Client/Transport 架构如何分层？
7. 如何评测一个 Agent？（任务成功率、token 成本、失败重试策略）