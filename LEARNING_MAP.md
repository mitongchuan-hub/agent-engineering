# 🗺️ Agent Harness 工程学习地图

> 📌 **当前状态**：37 个教学步骤已全部图文齐备（每步 = 可运行 code.py + 详细教学 README + 专属 SVG 架构图，共 45 张），一键回归 `scripts/check_all.py` 全绿。

> 学习 Agent 工程外壳（harness）的一套完整笔记：
> 原理 → 手写 → 源码精读 → 机制重建 → 集成应用。
> 覆盖：**37 个可运行教学步骤 + 4 份源码精读 + 1 个工程化应用**。

---

## 一、学习资产总览

| 资产 | 位置 | 形态 | 学习顺序 |
|---|---|---|---|
| **手写框架教学** | `learn-mini-agent/` | s01~s10 分步可运行 | ① 原理地基 |
| **codex 机制重建** | `agent-source/codex_learn/` | c01~c07 分步可运行 | ② 工程外壳 |
| **deepseek 机制重建** | `agent-source/deepseek_learn/` | d01~d07 分步可运行 | ② 可插拔架构 |
| **pi 机制重建** | `agent-source/pi_learn/` | p01~p07 分步可运行 | ② 事件驱动 |
| **claude 机制重建** | `agent-source/claude_learn/` | x01~x06 分步可运行 | ② 提示词生态 |
| **源码精读导览** | `agent-source/deepdive-*.md` | 4 份文档 | ③ 精读溯源 |
| **四家对比总表** | `agent-source/CODING_AGENTS_STRUCTURE.md` | 1 份文档 | ③ 横向对比 |
| **工程化应用** | `matcher-app/` | 真实项目 | ④ 集成应用 |

**学习路径**：
```
learn-mini-agent（手写框架，建立心智模型）
   └─► 读四家源码（对照原版，理解工程取舍）
        └─► 四家机制重建（用 Python 亲手复刻核心设计）
             └─► matcher-app（把所学沉淀成可运行的 Agent 应用）
```

> 每一章的形态：`问题（故事化）→ 方案（SVG 架构图）→ 原理（逐步拆解）→ 代码走读 → 试一下 → 练习 → 自测问答 → 接下来`

---

## 二、37 步索引（每步一句话）

### A. 手写框架（learn-mini-agent，10 步）

| 步 | 主题 | 一句话 | 知识点 |
|---|---|---|---|
| s01 | Agent Loop | 一个 while 循环就是 Agent 心脏 | `LLM→工具→回填` 循环伪代码 |
| s02 | 工具注册 | 函数签名自动生成 JSON Schema | 签名即 schema、单一事实来源 |
| s03 | LLM 客户端 | 模型无关（本地假服务器验证协议） | 协议统一 + base_url 自动补 /v1 |
| s04 | 上下文管理 | 预算窗口截断 | 不拆散工具问答对 |
| s05 | 应用（匹配打分） | 规则+LLM 混合架构 | 可计算归规则、可推理归 LLM |
| s06 | 评测集 | Oracle 用例回归 | 结论准确率+评分均误差+挂 CI |
| s07 | MCP 协议 | 从零实现 JSON-RPC+stdio | 生命周期四步、错误分层 |
| s08 | MCP×Agent | 动态外接 MCP 服务器 | 工具即插件、进程隔离 |
| s09 | 健壮性 | 参数兜底/错误自愈/迭代上限 | 失败=数据流，四道防线 |
| s10 | 综合 | 十步拼成完整应用 | 真实产物 report.md |

### B. codex_learn（7 步）· 工程外壳

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| c01 | Bash 即工具 | 万能执行器+黑名单预检 | unified_exec |
| c02 | 并行工具 | 两阶段（prepare串行→execute并发）+保序 | parallel.rs |
| c03 | 审批流 | 白名单/黑名单/缓存免审 | approvals.rs |
| c04 | 沙箱 | 默认拒绝+显式放行 | sandboxing.rs + bwrap |
| c05 | 上下文压缩 | 摘要+Pre/Post hooks+fallback | compact.rs |
| c06 | 会话持久化 | JSONL 断点恢复 | rollout_reconstruction |
| c07 | 多 Agent | 主 agent 派发子 agent | control.rs / role.rs |

### C. deepseek_learn（7 步）· 可插拔架构

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| d01 | turn/step 状态机 | 显式状态 vs 双层 while | agent-loop/agent.ts |
| d02 | 插件钩子 | waterfall 拦截/改写 | dispatch.waterfall |
| d03 | Inbox | 消息投递与处理解耦 | inbox.claim |
| d04 | 严格 schema | 参数守门员拦截幻觉 | core/tools |
| d05 | 子 Agent | Task/Report 契约+Driver 抽象 | subagent/* |
| d06 | 上下文裁剪 | 先剪工具结果再压历史 | compaction-pruner |
| d07 | 提示词组装 | 分节渲染+tool-order | system-prompt |

### D. pi_learn（7 步）· 事件驱动

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| p01 | 事件流 | Agent 全程变成事件 | agent-loop emit |
| p02 | steering | 用户中途插话排队注入 | getSteeringMessages |
| p03 | 并行工具 | 双轨制：事件完成序/消息发起序 | ToolExecutionMode |
| p04 | 失败进流 | 错误编码进流而非抛异常 | StreamFn 契约 |
| p05 | provider 层 | 40+ 家模型的统一抽象 | ai/providers |
| p06 | 分支压缩 | 沉岔路保主线 | branch-summarization |
| p07 | JSONL 会话 | 带 codec 版本化的存档 | session/jsonl |

### E. claude_learn（6 步）· 提示词生态

| 步 | 主题 | 一句话 | 对应源码 |
|---|---|---|---|
| x01 | 插件结构 | manifest + commands 目录 | plugins/code-review |
| x02 | allowed-tools | 声明式权限白名单 | commands/*.md YAML 头 |
| x03 | 多 Agent 剧本 | 成本分层 + 并行编排 | code-review.md |
| x04 | hooks | 执行瞬间拦截/改写 | examples/hooks |
| x05 | 命令入口 | /命令 即能力 | .claude/commands |
| x06 | 插件引擎 | 四层流水线合体 | 以上全部 |

### E. 源码精读（4 份文档）

| 文档 | 内容 |
|---|---|
| deepdive-codex.md | 代码地图(11文件) + 审批/压缩/沙箱拆解 + 阅读路线 |
| deepdive-deepseek-harness.md | 代码地图 + 状态机/插件钩子/subagent 拆解 |
| deepdive-pi.md | 代码地图 + StreamFn/并行/steering 拆解 |
| deepdive-claude-code.md | plugins/allowed-tools/多 agent 剧本拆解 |

---

## 三、学习路线（按时间预算选）

### ⚡ 速览（1 天）
```
s01 s02 s06 → s07 s08（MCP 闭环）→ 精读文档的"知识要点"节（40 分钟）
产出：能画主循环图、能讲 MCP、能答上下文/工具并行/多 Agent
```

### 📘 入门（3~5 天）
```
Day1-2: learn-mini-agent s01~s06
Day3:   s07~s10
Day4:   pi_learn p01 p03 p04 + codex_learn c03 c04 + deepseek_learn d02
Day5:   精读 2 份文档 + matcher-app 全文跑通
```

### 📗 系统学习（2 周）
```
第1周：learn-mini-agent 全 10 步，每步跑通并记笔记
第2周：四家教学 27 步（每天约 4 步）+ 精读 4 份文档 + 横向对比总表
```

### 📕 完整体系（4 周）
```
第1周：learn-mini-agent s01~s06
第2周：s07~s10 + 明确 matcher-app 的设计文档
第3周：codex_learn + deepseek_learn（14 步）
第4周：pi_learn（7 步）+ 4 份精读 + 三家用一句话各自总结
加餐：对照 4 份 deepdive 回读原版源码，把"机制重建 vs 原版"的差异记入笔记
```

---

## 四、知识点速查（14 题）

| 问题 | 答案骨架 | 在哪学 |
|---|---|---|
| Agent 主循环怎么写？ | 双层 while / 状态机 / 事件泵 三种 | s01 / d01 / p01 |
| Function Calling 协议？ | 签名→schema 自动生成 | s02 / d04 |
| 模型无关怎么做？ | ChatClient / provider 层 | s03 / p05 |
| Context 膨胀？ | 截断→压缩→裁剪；分支摘要 | s04 / c05 / d06 / p06 |
| 工具并行执行？ | 两阶段+保序；双轨事件 | c02 / p03 |
| 危险命令怎么防？ | 策略→审批→沙箱 三层 | c01 c03 c04 |
| 工具调用失败？ | 错误回传自愈；失败进流 | s09 / p04 |
| 多 Agent 怎么做？ | 转场控制 / 子 agent 契约 / 协议兼容 | c07 / d05 |
| 上下文丢了怎么办？ | JSONL 持久化 + codec 迁移 | c06 / p07 |
| 什么是 MCP？ | JSON-RPC+stdio；生命周期 4 步 | s07 s08 |
| 怎么评价 Agent？ | Oracle 回归 + 指标 + 冒烟 | s06 |
| 插件化怎么设计？ | waterfall 钩子；order 排序 | d02 |
| 系统提示词怎么管？ | 分节组装 + tool-order | d07 |
| 用户中途输入？ | steering 排队注入 | p02 |
| 提示词即软件？ | 插件=manifest+commands；白名单+钩子+剧本 | x01~x06 |

---

## 五、学习笔记沉淀建议

学完每个主题后，把三件事写进自己的笔记：
1. **一句话总结**：这个机制解决什么问题、trade-off 是什么（如"沙箱 vs 审批：能力的边界 vs 行为的决策"）
2. **最小实现**：不看源码，凭记忆写出核心循环（30 行内）
3. **与手写版对比**：我们的 sXX 和原版差在哪（差的就是生产级答案）

> 参考：四家源码 clone 在本地 `agent-source/` 下（不进仓库，供对照阅读）。

## 六、常用命令

```bash
python learn-mini-agent/s01_agent_loop/code.py        # 手写框架入口
python agent-source/codex_learn/c01_bash_tool/code.py  # codex 机制
python agent-source/deepseek_learn/d01_turn_step_loop/code.py
python agent-source/pi_learn/p01_event_stream/code.py
python matcher-app/run.py --mock                     # 工程化应用（无 Key）
python matcher-app/run.py --verbose                  # 配 .env 走真实 LLM
```
> 环境：测试用 Python 3.12；matcher-app 自带 .venv。密钥（.env）不入仓库。