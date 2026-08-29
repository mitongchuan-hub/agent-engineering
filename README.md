# Agent Harness 工程学习笔记

> 从零手写一个 Agent 框架，再逐一拆解 codex / deepseek-harness / pi / claude-code
> 四家开源 harness（Agent 工程外壳）的实现与设计取舍。
> 全部代码无需 API Key 即可运行（内置演示模型），配 Key 走真实大模型。

## 内容导航

| 目录/文件 | 内容 |
|---|---|
| `learn-mini-agent/` | **s01~s10** 从零手写框架：循环 → 工具注册 → LLM 客户端 → 上下文 → 应用 → 评测 → MCP → 健壮性 |
| `agent-source/codex_learn/` | **c01~c07** codex 机制重建：Bash 工具 / 并行 / 审批 / 沙箱 / 压缩 / 持久化 / 多 Agent |
| `agent-source/deepseek_learn/` | **d01~d07** deepseek 机制重建：状态机 / 插件钩子 / Inbox / 严格 Schema / 子 Agent / 裁剪 / 提示词组装 |
| `agent-source/pi_learn/` | **p01~p07** pi 机制重建：事件流 / steering / 并行双轨 / 失败进流 / Provider / 分支压缩 / JSONL |
| `agent-source/claude_learn/` | **x01~x06** claude 机制重建：插件结构 / 白名单 / 多 Agent 剧本 / hooks / 命令 / 引擎 |
| `agent-source/deepdive-*.md` | 四家源码精读导览（代码地图 + 机制拆解 + 阅读路线） |
| `agent-source/CODING_AGENTS_STRUCTURE.md` | 四家核心循环/工具/上下文 横向对比总表 |
| `matcher-app/` | 基于所学实现的工程化 Agent 应用（评测/单测/MCP/真实 LLM 自主决策） |
| `LEARNING_MAP.md` | 学习总地图：37 步索引 + 路线规划 + 知识点速查 |

> 📖 所有教学步骤均为同一详细度：**故事化问题 + SVG 架构图 + 逐步原理 + 练习 + 自测问答 + 源码对照**（全库 45 张架构图）。

## 快速开始

```bash
# ① 手写框架（从第一个 while 循环开始）
python learn-mini-agent/s01_agent_loop/code.py

# ② 机制重建（21 步全可跑）
python agent-source/codex_learn/c01_bash_tool/code.py
python agent-source/deepseek_learn/d01_turn_step_loop/code.py
python agent-source/pi_learn/p01_event_stream/code.py
python agent-source/claude_learn/x01_plugin_manifest/code.py

# ③ 工程化应用（Mock 无需 Key / 配 .env 走真实 LLM）
python matcher-app/run.py --mock
python matcher-app/run.py --verbose
```

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

## 学习主题

- **主循环**：双层 while / turn-step 状态机 / 事件泵三种形态的取舍
- **工具系统**：函数签名→Schema 自动生成、并行执行与保序、错误回传自愈
- **上下文**：窗口截断 → 摘要压缩 → 分支压缩 → 工具结果裁剪的演进
- **工程外壳**：审批流、沙箱、会话持久化（JSONL + codec 版本化）
- **协议**：MCP 从零实现（JSON-RPC + stdio），Agent 动态外接
- **架构**：插件钩子（waterfall）、Provider 层模型无关、事件驱动可观测性

## 环境与密钥

- **Python** 3.12（教学演示无需任何第三方库）；真实 LLM 模式需 `openai`：`pip install -r requirements.txt`
- **密钥**：统一放仓库根 `.env`（已被 .gitignore 排除，不会提交）；不配 Key 时全部代码走内置演示模型
- **一键回归**：`python scripts/check_all.py`（35 步教学 + 应用单测 + 评测集）
- **CI**：`.github/workflows/ci.yml`（push 时自动跑上述回归，均无需 Key）