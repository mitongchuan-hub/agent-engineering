# 第 10 章：上下文压缩与恢复

## 本章问题

上下文迟早会超过模型窗口，Provider 也可能返回 error 或 length stop。Pi 没有简单地删除旧列表，而是把恢复拆成：

```text
检测 overflow/threshold
  -> prepareCompaction()
  -> 生成 summary
  -> 写入 compaction entry
  -> 重建当前 context
  -> 必要时 retry 一次
```

## 源码调用链

```text
AgentSession._handlePostAgentRun()
  -> _prepareRetry(error)
  -> _checkCompaction(assistantMessage)
     -> prepareCompaction(pathEntries, settings)
     -> _runAutoCompaction(reason, willRetry)
        -> compact(preparation, ...)
        -> SessionManager.appendCompaction(...)
        -> buildSessionContext()
        -> agent.continue()       # overflow retry
```

## 压缩切点

`prepareCompaction()` 从新到旧累计估算 token，选择最近的合法切点：

- 可以切在 user 或 assistant 消息。
- 不能切在 tool result 上，因为 tool result 必须跟随对应调用。
- 如果切在一个 turn 中间，会把 turn 开头单独作为 prefix summary。
- `firstKeptEntryId` 记录保留尾部的第一个 Session entry。

本章使用 Pi 同样的教学级 chars/4 估算。真实 token 统计会优先使用 Provider usage。

## Compaction entry

压缩不是删除旧 JSONL 行，而是追加一条 compaction entry：

```text
旧历史 ... -> compaction(summary, firstKeptEntryId) -> 新消息 ...
```

重新构建 context 时，最新 summary 放在前面，再接从 `firstKeptEntryId` 开始的保留路径和压缩后的新消息。旧 entry 仍然存在，可用于审计、分支和再次恢复。

## Retry 与 Overflow Recovery

两类恢复不要混淆：

- transient error：按 retry policy 重试，不必压缩。
- context overflow / recoverable length：先压缩，再最多 retry 一次。
- aborted：用户取消，不自动压缩，也不自动 retry。
- 第二次 overflow：报告失败，不能无限 compact-and-retry。

overflow retry 时，失败的 assistant message 仍可留在 Session 历史，但必须从 retry context 排除；否则模型会把失败响应当作正常上下文继续推理。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s10_context_recovery/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s10_context_recovery.py
```

示例会模拟 length stop，生成摘要，排除失败响应，并将恢复后的 assistant 追加到新边界之后。

## 关键测试

- 切点永远不落在 tool result。
- split turn 的 prefix 独立摘要。
- compaction entry 保存 summary、首个 kept id 和压缩前 token。
- summary 能重建为“摘要 + 保留尾部”。
- reserve token 会影响 threshold 判断。
- transient error 只 retry，不触发 compaction。
- aborted 跳过 compaction 和 retry。
- overflow compact-and-retry 一次，失败响应不进入 retry context。
- 第二次 overflow 不再重复压缩。
- branch summary 只基于分支消息生成。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| summarizer 是离线 callable | Pi 使用模型生成结构化 summary，并带 retry policy |
| token 使用 chars/4 | Pi 优先使用 assistant usage，再估算 trailing messages |
| Session entry 使用内存列表 | Pi 追加写入 v3 JSONL 并维护索引 |
| retry response 由调用方提供 | Pi 通过 Agent continue 和动态 Provider 请求恢复 |
| file operations 未追踪 | Pi 的 compaction details 会记录 read/modified files |

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`compaction.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/compaction/compaction.ts)：`estimateTokens`、`findCutPoint`、`prepareCompaction`、`compact`。
- [`agent-session.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/agent-session.ts)：`_checkCompaction`、`_runAutoCompaction`、`_prepareRetry`。
- [`session-manager.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/session-manager.ts)：`buildContextEntries`、`appendCompaction`、`buildSessionContext`。
- [`compaction.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/test/compaction.test.ts)：切点、summary 和 compaction context 测试。
- [`agent-session-auto-compaction-queue.test.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/test/agent-session-auto-compaction-queue.test.ts)：overflow、threshold 和避免重复恢复测试。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 11 章进入扩展与资源边界，研究自定义工具和资源如何接入，而不改写核心 loop。
