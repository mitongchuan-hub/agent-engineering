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
| `resume-matcher/` | 工程化 Agent 应用成品 | 15 单测 + 6 评测用例 + MCP + 真实 LLM 自主决策 |
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

## 🎬 Demo 输出（均为真实运行记录）

### ① 评测集回归（Oracle 用例）

```
[PASS] case_backend_full:   score=100.0 (期望 95~100), verdict=强烈推荐
[PASS] case_ai_missing_es:  score=91.5  (期望 85~95),  verdict=强烈推荐
[PASS] case_ai_low_edu:     score=66.5  (期望 60~75),  verdict=推荐
[PASS] case_years_fail:     score=75.0  (期望 70~80),  verdict=推荐
...
========== 评测汇总 ==========
  结论准确率 : 100% (6/6)
  评分均误差 : 0.00 分
  结果       : ✅ 全部通过（exit=0，可挂 CI）
```

### ② MCP 协议生命周期（从零实现，无官方 SDK）

```
① initialize -> protocolVersion=2024-11-05, server=mini-mcp-server
② tools/list -> 发现 1 个工具: ['compute_match']
③ tools/call compute_match -> 总分 91.5（isError=False）
④ 未知工具 -> JSON-RPC error: 未知工具: not_exist
⑤ 参数不全 -> result.isError=True（业务错误 vs 协议错误分层）
```

### ③ Agent 自主决策（真实 LLM，6 步零人类干预）

```
step 1: list_files ×2（探索目录）
step 2: read_text_file ×3（读取输入文件）
step 3: compute_match ×2（规则打分器）
step 4: write_file（输出结构化工单报告）
step 5: 模型给出最终总结，循环结束
上下文统计：{total_msgs: 15, used_chars: 11508 / 24000}
```

> 全部教学代码无需 API Key（内置演示模型，`python xxx/code.py` 即跑即出）。
```

> 本仓库所有教学代码无需 API Key（内置演示模型）；`.env` 密钥已排除，不提交。