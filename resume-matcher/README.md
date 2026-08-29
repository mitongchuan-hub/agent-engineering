# Resume × JD 匹配 Agent（秋招作品集项目）

从零手写 Mini Agent 框架（无第三方框架依赖），再在其上实现「简历 × 岗位 JD 匹配 Agent」。
**面试价值**：既能讲清楚 Agent 原理（ReAct / function calling / 上下文管理），又有完整可跑的应用与报告产出。

## 架构一览

```
run.py  (CLI 入口)
  │
  ├─ 无 key ──▶ app/main.py::run_mock_pipeline  确定性规则管线（CI/联调用）
  │
  └─ 有 key ──▶ app/main.py::build_agent
                  │
                  ▼
        ┌────────────────────────────┐
        │      Agent (ReAct 循环)     │
        │  while 模型还要调工具:       │
        │    LLM(messages, tools)     │
        │    └ 执行 tool_calls        │
        └──────┬───────────┬─────────┘
               │           │
        mini_agent/    app/tools.py（领域工具）
        ├ tools.py    ├ list_files / read_text_file
        │  函数签名→JSON Schema  ├ compute_match（规则打分器）
        ├ llm.py      └ write_file（保存报告）
        │  OpenAI 兼容客户端
        ├ memory.py
        │  上下文预算窗口截断
        └ agent.py（主循环）
```

## 三类面试题对应代码位置

| 面试题 | 答案在 | 一句话答案 |
|---|---|---|
| Function calling 协议是什么？ | `mini_agent/tools.py` | 函数签名 + type hints 自动生成 JSON Schema；`registry.call` 执行并把结果以字符串回填 |
| Agent 主循环怎么写？ | `mini_agent/agent.py` | `循环 { LLM 生成 → 解析 tool_calls → 执行工具 → tool 消息回填 }`，无 tool_calls 即结束 |
| Context 无限膨胀怎么办？ | `mini_agent/memory.py` | 窗口截断（保留 system + 尾部回合），生产常配摘要压缩 + 向量检索 |
| 工具调用失败了怎么办？ | `registry.call` 异常分支 | 错误以字符串回传模型，让模型自愈重试；配迭代上限兜底死循环 |
| 为什么规则 + LLM 混合？ | `app/tools.py: compute_match` | 可计算的事交给确定性工具（可审计可复现），推理交给 LLM |
| OpenAI 兼容协议怎么做模型无关？ | `mini_agent/llm.py` | ChatClient 封装 base_url/model 差异，自动补 /v1 |
| MCP 是什么？协议怎么走？ | `mini_agent/mcp.py` | JSON-RPC 2.0 + stdio 传输：initialize → initialized 通知 → tools/list → tools/call；业务错误走 isError，协议错误走 error 字段 |
| Agent 怎么评估效果？ | `eval/run_eval.py` | Oracle 用例回归：结论准确率 + 评分均误差 + 端到端冒烟；挂 CI 防打分器跑偏 |

## 快速开始

```bash
cd resume-matcher
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# ① 无 key 先跑通（Mock 模式，确定性管线）：
python run.py --mock --verbose

# ② 配置 LLM key 后跑真 Agent：
#    复制 .env.example 为 .env 并填入 key（或设置环境变量）
python run.py --verbose

# ③ MCP 协议演示（无需 key）：
python demo_mcp.py --cli

# ④ Agent 通过 MCP 动态连接外部服务器（需要 key）：
python demo_mcp.py

# ⑤ 评测集（无需 key，可挂 CI）：
python eval/run_eval.py -v
python eval/run_eval.py --smoke

# ⑥ 全部单测（15 个，含假 OpenAI 服务器协议联调 + MCP 子进程级联调）：
python -m unittest discover -s tests
```

## 配置 LLM（任选，都是 OpenAI 兼容协议）

| 服务商 | base_url | model |
|---|---|---|
| DeepSeek（推荐，便宜直连） | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |

环境变量方式（不污染代码）：

```bash
$env:LLM_API_KEY="sk-xxx"; $env:LLM_BASE_URL="https://api.deepseek.com/v1"; $env:LLM_MODEL="deepseek-chat"
python run.py --verbose
```

## 产物

- `reports/match_report.md` —— Agent 自动生成的结构化匹配报告（真模式）或规则报告（Mock 模式）

## 项目代码怎么读（建议顺序）

1. `mini_agent/tools.py` → 工具注册与 schema 生成（最容易）
2. `mini_agent/agent.py` → ReAct 主循环（最重要的 60 行）
3. `mini_agent/memory.py` → 上下文管理
4. `app/tools.py` `compute_match` → 规则打分器
5. `app/main.py` `SYSTEM_PROMPT` → 用提示词做工作流编排
6. `mini_agent/mcp.py` → MCP 协议（JSON-RPC 生命周期）
7. `eval/cases.py` + `eval/run_eval.py` → 评测集设计

## 已完成的能力（全部有测试）

- [x] 手写 Agent 框架：ReAct 循环 / schema 自动生成 / 上下文管理 / 工具异常自愈
- [x] 评测集：6 个 Oracle 用例（结论准确率 + 评分均误差 + 端到端冒烟）
- [x] MCP：从零实现协议层（stdio + JSON-RPC），Agent 可动态连接外部 MCP Server
- [x] 15 个单测含两大联调：假 OpenAI 服务器协议联调、MCP 子进程级联调

## 下一步扩展（面试加分方向）

- [ ] 向量检索版 RAG：给 Agent 加 `search_jd_by_keyword` 工具
- [ ] 多 Agent：HR 评审 Agent + 候选人自评 Agent 双角色对撞
- [ ] LLM 报告质量评测：人工标注 20 份报告，与 LLM 报告算相关度（把评测问卷层、不再只看打分器）

> 本项目为教学演示，技能匹配用词表近似；生产环境建议换向量语义匹配 + 结构化简历解析。