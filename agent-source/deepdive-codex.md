# DEEP DIVE: openai/codex（Rust）

> 源码：`agent-source/codex/` ｜ 语言：Rust ｜ 规模：monorepo 100+ crates，核心 6750 文件
> 定位：OpenAI 官方 Coding Agent CLI，**生产级工程化的教科书**
> 阅读难度：★★★★★（建议按本章"代码地图"只挑核心读，不要通读）

## 一、定位

codex 的价值不在"Agent 循环"（那是所有 agent 最没看点的地方），
而在**工程外壳**：沙箱、审批、持久化、上下文压缩、MCP、多 agent——
这些才是生产级与教学级的差距。读它 = 学"Agent 怎么在真实环境站得住"。

## 二、代码地图（按学习顺序）

| 顺序 | 文件 | 行数 | 内容 | 优先级 |
|---|---|---|---|---|
| 1 | `codex-rs/core/src/client.rs` | 111KB | 会话客户端（最大的入口文件） | 🔍 选读关键函数 |
| 2 | `codex-rs/core/src/codex_thread.rs` | 37KB | 线程模型（一次持续会话） | 🔍 |
| 3 | `codex-rs/core/src/session/mod.rs` | 183KB | Session 主类型：spawn/submit/next_event 事件泵 | 🔍 必读架构 |
| 4 | `codex-rs/core/src/tools/approvals.rs` | 35KB | **审批流**（本章重点） | ⭐ 精读 |
| 5 | `codex-rs/core/src/tools/registry.rs` | 32KB | 工具注册表 | ⭐ 精读 |
| 6 | `codex-rs/core/src/tools/parallel.rs` | 27KB | 并行工具执行 | ⭐ 精读 |
| 7 | `codex-rs/core/src/compact.rs` | 30KB | 上下文压缩 + **pre/post compact hooks** | ⭐ 精读 |
| 8 | `codex-rs/core/src/sandboxing/` | - | 沙箱（mod.rs 是联合入口） | ⭐ 精读 |
| 9 | `codex-rs/core/src/agent/control.rs` | 33KB | 多 agent 转场控制 | 🔍 |
| 10 | `linux-sandbox/` `windows-sandbox-rs/` | - | 平台级沙箱 | 📖 看 README |
| 11 | `codex-mcp/` `mcp-server/` `rmcp-client/` | - | MCP 全栈（server+client） | 📖 |

## 三、核心机制拆解

### ① 审批流（approvals.rs）——"危险操作三检查"

```
工具触发权限请求（如执行命令、访问网络）
   │
   ├─ ① exec_policy          命令匹配策略（预置黑白名单）
   ├─ ② guardian             AI 审查路由（生成审查理由供用户参考）
   ├─ ③ permission hooks     用户自定义钩子（无头 CI 场景忽略/通过）
   └─ 决策：批准 / 拒绝 / 限时 / 缓存（with_cached_approval 短时间内免审）
```
亮点：`with_cached_approval`——同一会话短期内同类操作免重复审批，
平衡安全与流畅。

### ② 上下文压缩（compact.rs）——两层钩子包住压缩

```
触发：超过 token 预算
  PreCompactHook（压缩前：可拦截/自定义策略）
    └─ 调用 LLM 生成摘要（CompactionSummary）
  PostCompactHook（压缩后：校验/记录）
ctx：WorldState（世界状态快照，压缩时保持一致）
```
对应我们 mini_agent 的 `memory.py`：codex 把"压缩"做成了**钩子环绕的正式流程**，
还带 `compact_model_fallback.rs`（主模型不可用→换便宜模型）。

### ③ 沙箱三层

| 层 | 实现 | 说明 |
|---|---|---|
| Linux 用户态 | `linux-sandbox`（bwrap） | 非特权沙箱，命令隔离 |
| Windows | `windows-sandbox-rs` | Windows 侧作业对象/ACL |
| 统一 | `core/src/sandboxing.rs` | 平台无关的策略层 |

## 四、三档阅读路线

- **30 分钟**：读 `tools/registry.rs` 顶部 + `approvals.rs` 顶部注释 + `compact.rs` 顶部注释（认架构，不读实现）
- **半天**：registry → parallel → approvals 三连，能讲清"工具怎么注册/并发/审批"
- **3 周**：session 事件泵 → sandboxing → compact → agent/control，边读边在 Rust 里运行 `cargo test` 的对应测试

## 五、面试考点（回答即加分）

1. "你的 Agent 怎么安全执行命令？" → codex 三件套：策略匹配 + 沙箱 + 审批流
2. "上下文爆了怎么办？" → 压缩 hooks + 摘要 + model fallback（比"截断"高一级）
3. "并行工具调用怎么保证一致性？" → parallel.rs 的分阶段执行（先 prepare 后 execute）
4. "会话能恢复吗？" → session/rollout_reconstruction.rs（81KB 回放重建）

## 六、动手练习

1. 搜 `with_cached_approval` 调用点，画出审批缓存的时效逻辑
2. 读 `parallel.rs` 的 prepare→execute 两阶段，和 pi 的 parallel 模式对比（见 pi 精读）
3. 在 `codex-rs/core/src/tools/handlers/` 里找 `unified_exec`，看一个真实工具怎么落地