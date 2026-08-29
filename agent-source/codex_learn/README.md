# codex_learn —— 用 Python 重建 codex 的核心机制（分步教学）

> 配套源码：`agent-source/codex/`（Rust 原版）
> 教学方式：每步一个可运行 Python 文件，重建 codex 的一个关键设计，配自测问答。
> 与 learn-mini-agent 的关系：那边教你写框架，这里教你学工程外壳。

## 步骤导航

| 步骤 | 主题 | 对应 codex 源码 | 你能掌握 |
|---|---|---|---|
| [c01](c01_bash_tool/) | Bash 即工具 | `tools/handlers/unified_exec` | "Bash is all you need"哲学 + 命令执行工具 |
| [c02](c02_parallel_tools/) | 工具并行执行 | `tools/parallel.rs` | 两阶段（prepare→execute）+ 回填保序 |
| [c03](c03_approvals/) | 审批流 | `tools/approvals.rs` | 白名单/黑名单/缓存审批（危险操作可控） |
| c04 | 沙箱 | `sandboxing.rs` + `linux-sandbox` | 允许列表 + 超时 + 降权，命令隔离 |
| c05 | 上下文压缩 | `compact.rs` | 预算触发 + 摘要 + Pre/Post 钩子 |
| c06 | 会话持久化 | `session/rollout_reconstruction.rs` | JSONL 存档 / 断点恢复 |
| c07 | 多 Agent | `agent/control.rs` + `role.rs` | 子 Agent 分工与转场 |

## 怎么跑

```bash
# 任意一步，无需 Key：
python agent-source/codex_learn/c01_bash_tool/code.py
```

## 自测一句话（学完说这个系列）

> "我精读过 openai/codex 的 Rust 源码，并用 Python 重建了它的并行工具执行、
> 审批流和沙箱模型——生产级 Agent 的工程外壳，我手上过一遍。"