# 🗺️ 秋招 Agent 学习体系总地图（LEARNING MAP）

> 目标：一套从"原理 → 手写 → 源码精读 → 重建机制"的完整 Agent 备战体系。
> 覆盖：**38 个可运行教学步骤 + 4 份源码精读 + 1 个完整成品项目 + 21 家考点**
> 全部代码无需 API Key 即可运行（内置演示模型），配 Key 走真实大模型。

---

## 一、四大学习资产总览

| 资产 | 位置 | 形态 | 定位（先学哪个） |
|---|---|---|---|
| **手写框架教学** | `learn-mini-agent/` | s01~s10 分步可运行 | ① 原理地基：循环→工具→客户端→内存→应用→评测→MCP→健壮性 |
| **codex 源码教学** | `agent-source/codex_learn/` | c01~c07 分步可运行 | ② 工程外壳：并行/审批/沙箱/压缩/持久化/多 agent |
| **deepseek 源码教学** | `agent-source/deepseek_learn/` | d01~d07 分步可运行 | ② 可插拔架构：状态机/插件钩子/Inbox/schema/子 agent |
| **pi 源码教学** | `agent-source/pi_learn/` | p01~p07 分步可运行 | ② 现代 Agent：事件流/steering/双轨并行/失败进流/provider |
| **源码精读导览** | `agent-source/deepdive-*.md` | 4 份文档 | ③ 面试冲刺：代码地图+机制拆解+考点清单 |
| **四家对比总表** | `agent-source/CODING_AGENTS_STRUCTURE.md` | 1 份文档 | ③ 横切对比：循环模型/工具/上下文/多 agent |
| **完整成品项目** | `resume-matcher/` | 真实项目 | ④ 简历展示：15 单测+评测集+MCP+.env |
| **调研总报告** | `agent_projects_research.md` | 1 份文档 | 项目选型与秋招情报 |

**关系图**：
```
learn-mini-agent（你写框架）
   └─► 读四家源码（懂为什么这么写）
        └─► 三家教学（用 Python 重建它们的机制）
             └─► resume-matcher（结合所有认知的成品）
                  └─► 简历/面试输出
```

---

## 二、38 步完整地图（每步一句话）

### A. 手写框架（learn-mini-agent，10 步）——自己造轮子

| 步 | 主题 | 一句话 | 核心面试点 |
|---|---|---|---|
| s01 | Agent Loop | 一个 while 循环就是 Agent 心脏 | `LLM→工具→回填` 循环伪代码 |
| s02 | 工具注册 | 函数签名自动生成 JSON Schema | 签名即 schema、单一事实来源 |
| s03 | LLM 客户端 | 模型无关（假服务器验证协议） | 协议统一 + base_url 自动补 /v1 |
| s04 | 上下文管理 | 预算窗口截断 | 不拆散工具问答对、三解法 |
| s05 | 简历匹配应用 | 规则+LLM 混合架构 | 可计算归规则、可推理归 LLM |
| s06 | 评测集 | Oracle 用例回归 | 结论准确率+评分均误差+挂 CI |
| s07 | MCP 协议 | 从零实现 JSON-RPC+stdio | 生命周期四步、错误分层 |
| s08 | MCP×Agent | 动态外接 MCP 服务器 | 工具即插件、进程隔离 |
| s09 | 健壮性 | 参数兜底/错误自愈/迭代上限 | 失败=数据流，四道防线 |
| s10 | 综合 | 10 步拼成完整应用 | 真实报告产物 report.md |

### B. codex_learn（7 步）——工程外壳

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| c01 | Bash 即工具 | 万能执行器+黑名单预检 | unified_exec |
| c02 | 并行工具 | 两阶段（prepare串行→execute并发）+保序 | parallel.rs |
| c03 | 审批流 | 白名单/黑名单/缓存免审 | approvals.rs |
| c04 | 沙箱 | 默认拒绝+显式放行 | sandboxing.rs + bwrap |
| c05 | 上下文压缩 | 摘要+Pre/Post hooks+fallback | compact.rs |
| c06 | 会话持久化 | JSONL 断点恢复 | rollout_reconstruction |
| c07 | 多 Agent | 主 agent 派发子 agent | control.rs / role.rs |

### C. deepseek_learn（7 步）——可插拔架构

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| d01 | turn/step 状态机 | 显式状态 vs 双层 while | agent-loop/agent.ts |
| d02 | 插件钩子 | waterfall 拦截/改写 | dispatch.waterfall |
| d03 | Inbox | 消息投递与处理解耦 | inbox.claim |
| d04 | 严格 schema | 参数守门员拦截幻觉 | core/tools |
| d05 | 子 Agent | Task/Report 契约+Driver 抽象 | subagent/* |
| d06 | 上下文裁剪 | 先剪工具结果再压历史 | compaction-pruner |
| d07 | 提示词组装 | 分节渲染+tool-order | system-prompt |

### D. pi_learn（7 步）——现代事件驱动

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| p01 | 事件流 | Agent 全程变成事件 | agent-loop emit |
| p02 | steering | 用户中途插话排队注入 | getSteeringMessages |
| p03 | 并行工具 | 双轨制：事件完成序/消息发起序 | ToolExecutionMode |
| p04 | 失败进流 | 错误编码进流而非抛异常 | StreamFn 契约 |
| p05 | provider 层 | 40+ 家模型的统一抽象 | ai/providers |
| p06 | 分支压缩 | 沉岔路保主线 | branch-summarization |
| p07 | JSONL 会话 | 带 codec 版本化的存档 | session/jsonl |

### E. 源码精读（4 份文档，不写代码）

| 文档 | 内容 |
|---|---|
| deepdive-codex.md | 代码地图(11文件) + 审批/压缩/沙箱拆解 + 阅读路线+考点 |
| deepdive-deepseek-harness.md | 代码地图 + 状态机/插件钩子/subagent 拆解 |
| deepdive-pi.md | 代码地图 + StreamFn/并行/steering 拆解 |
| deepdive-claude-code.md | plugins/allowed-tools/多 agent 剧本拆解 |
| CODING_AGENTS_STRUCTURE.md | 四家横向对比总表（8 维度） |

---

## 三、学习路线（按剩余时间选）

### 🕐 只剩 3 天（面试突击）
```
Day1: s01 s02 s06 + 精读文档的"面试考点"节（4份共40分钟）
Day2: s07 s08（MCP 完整闭环）+ 背"四家速查表"（agent-source/README.md）
Day3: 把 resume-matcher 跑一遍（mock + 真实各一次）+ 过一遍本项目问题清单
产出：能画循环图、能讲 MCP、能答上下文/多agent/评测
```

### 🕑 7 天（小冲刺）
```
Day1-2: learn-mini-agent s01~s06（框架+应用+评测）
Day3-4: s07~s10（MCP 两条 + 健壮性 + 综合）
Day5:   pi_learn p01 p03 p04（事件流/并行/失败进流——最高频考点）
Day6:   codex_learn c03 c04（审批/沙箱——安全必问）+ deepseek d02（插件钩子）
Day7:   精读文档考点 30 分钟 + resume-matcher 全文跑通 + 简历文案定稿
```

### 🕒 14 天（标准备战）
```
第1周：learn-mini-agent 全 10 步，每步跑通+写要点笔记
第2周：三家教学 21 步（每天 3 步）+ 精读 2 份文档 + 综述对比表
产出：一份"面试题→答案→代码位置"的速查笔记（本文档第三节即骨架）
```

### 🗓 30 天（完整备战）
```
第1周：learn-mini-agent s01~s06
第2周：s07~s10 + 明确 resume-matcher 演讲故事线
第3周：codex_learn(c01-07) + deepseek_learn(d01-07)
第4周：pi_learn(p01-07) + 4 份精读 + 复盘三家用一句话概括
备选加餐：给 resume-matcher 提一个"生产级缺口"（审批/会话持久化/事件流）
```

---

## 四、面试考点 → 学哪里 速查表

| 面试题 | 答案骨架 | 在哪个步骤 |
|---|---|---|
| Agent 主循环怎么写？ | 双层 while / 状态机 / 事件泵 三种 | s01 / d01 / p01 |
| Function Calling 协议？ | 签名→schema 自动生成 | s02 / d04 |
| 模型无关怎么做？ | ChatClient / provider 层 | s03 / p05 |
| Context 膨胀？ | 截断→压缩→检索；工具结果裁剪 | s04 / c05 / d06 / p06 |
| 工具并行执行？ | 两阶段+保序；双轨事件 | c02 / p03 |
| 危险命令怎么防？ | 策略→审批→沙箱 三层 | c01 c03 c04 |
| 工具调用失败？ | 错误回传自愈；失败进流 | s09 / p04 |
| 多 Agent 怎么做？ | 转场控制 / 子 agent 契约 / 协议兼容 | c07 / d05 |
| 上下文丢了怎么办？ | JSONL 持久化+codec 迁移 | c06 / p07 |
| 什么是 MCP？ | JSON-RPC+stdio；生命周期 4 步 | s07 s08 |
| 怎么评价 Agent？ | Oracle 回归 + 指标 + 冒烟 | s06 |
| 插件化怎么设计？ | waterfall 钩子；order 排序 | d02 |
| 系统提示词怎么管？ | 分节组装 + tool-order | d07 |
| 用户中途输入？ | steering 排队注入 | p02 |
| 四家 agent 各自特点？ | Rust巨兽/一切皆插件/事件流/提示词生态 | 精读 4 份 |

---

## 五、简历素材库（写什么、从哪来）

| 简历条目（推荐写法） | 依据 |
|---|---|
| "从零手写 Agent 框架：ReAct 循环、工具 Schema 自动生成、上下文预算管理" | learn-mini-agent s01 s02 s04 |
| "规则打分器+LLM 推理混合架构，输出可审计可复现的匹配报告" | s05 |
| "自建评测集：6 个 Oracle 用例，结论准确率 100%，可挂 CI" | s06 |
| "从零实现 MCP 协议（JSON-RPC+stdio），Agent 动态外接外部服务器" | s07 s08 |
| "精读 openai/codex、deepseek-harness、pi 源码并手写重建其核心机制" | agent-source 三家教学 |
| "生产级健壮性：参数类型兜底、错误回传自愈、迭代上限" | s09 |
| 完整项目：resume-matcher（15 单测 + 评测集 + Mock 管线无 Key 可跑） | resume-matcher |

**面试启动句**：
> "我手写了 Agent 框架（讲原理），逐家精读了三个主流源码并用 Python 重建机制（讲深度），最后沉淀成 resume-matcher 完整应用（讲落地）——从原理到工程一条线。"

---

## 六、日常使用命令速查

```bash
# 手写框架教学（任意一步，无需 Key）
python learn-mini-agent/s01_agent_loop/code.py

# 三家源码教学（21 步全可跑）
python agent-source/codex_learn/c01_bash_tool/code.py
python agent-source/deepseek_learn/d01_turn_step_loop/code.py
python agent-source/pi_learn/p01_event_stream/code.py

# 完整成品项目（Mock 管线 / 真实 LLM）
python resume-matcher/run.py --mock
python resume-matcher/run.py --verbose          # 配 .env 后

# 全量测试（37 步 + resume-matcher 15 单测）
python resume-matcher/.venv/Scripts/python.exe -m unittest discover -s resume-matcher/tests
```

> 环境：项目使用 `E:\python\jieshiqi\python.exe`（Python 3.12）；resume-matcher 有自己的 .venv。
> 提示：`.env` 只需一份在 resume-matcher/（含真实 Key），学习库会自动读取（无则演示模式）。