# 第 12 章：综合 Coding Agent

## 本章问题

前 11 章分别验证了 Agent 的核心机制。本章不再增加新的隐藏规则，而是把它们组合成一个边界清晰、可离线测试、可替换 Provider 的 Coding Agent。

```text
Extension API
      -> ToolRegistry
      -> ComprehensiveAgent
         -> ContextPolicy -> Provider
         -> ToolResult -> SessionStore
         -> RecoveryPolicy
```

## 组合关系

| 模块 | 负责什么 | 不负责什么 |
|---|---|---|
| `models.py` | 定义消息、tool call 和序列化 | 不请求模型 |
| `provider.py` | 暴露模型请求边界 | 不执行工具 |
| `tools.py` | 注册和批量执行工具 | 不持久化 transcript |
| `context.py` | transform、过滤和请求快照 | 不改变 Session 历史 |
| `session.py` | JSONL header、entry、leaf 和 branch | 不决定模型行为 |
| `recovery.py` | 阈值/length 的压缩适配 | 不实现真实摘要模型 |
| `extensions.py` | 通过窄 API 注册工具 | 不直接修改 Agent Loop |
| `agent.py` | 组织 prompt、请求、工具回环和结束 | 不把所有机制写死在工具中 |

## 主调用链

```text
prompt
  -> SessionStore.append_message(user)
  -> ContextPolicy.build()
  -> Provider.complete()
  -> append assistant
  ->
     toolUse: ToolRegistry.execute_batch()
               -> append toolResult
               -> 下一轮 Provider
     stop:    agent_end -> agent_settled
     length:  RecoveryPolicy.compact()
               -> 排除失败响应
               -> retry 一次
```

核心 `ComprehensiveAgent` 只负责编排，所有跨模块数据都通过明确对象传递。真实 Provider 可以替换 `ScriptedProvider`，而不用改工具注册、Session 或上下文策略。

## 动手运行

从仓库根目录执行：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s12_comprehensive/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s12_comprehensive.py
```

示例使用扩展注册 `read_memory_file`，Provider 第一次返回 tool call，第二次读取 tool result 后完成回答。Session 文件写入 `.task-output/s12-demo/session.jsonl`。

## 关键测试

- 工具调用能完成完整的两轮闭环。
- 扩展工具进入同一工具池，不需要修改 Agent Loop。
- notification 在模型请求前被过滤。
- Session 可重新打开并恢复 transcript。
- branch 保留旧路径并切换活动 leaf。
- 并行工具完成顺序和结果顺序保持不同但正确。
- length stop 触发 compact-and-retry，失败响应不进入下一次请求。
- Provider 异常变成 error assistant，并以 settled 结束。

## 与 Pi 的差异

本章是可运行的 Python 教学 Harness，不是 Pi 的完整移植：

- Provider 使用脚本响应，没有真实网络协议适配。
- 事件使用简单 `AgentEvent` 记录，没有完整 ExtensionRunner 总线。
- 工具 schema、图片内容、usage 和 UI renderer 被压缩为最小接口。
- Session 采用轻量 JSONL 实现，未覆盖所有 metadata、label 和 migration 分支。
- Recovery 使用确定性摘要，不调用 summarization Provider。
- CLI、print/json、RPC 和 SDK 仍是外层接入附录。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`<br>
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`agent-loop.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent-loop.ts)：Agent Loop 和工具结果回环。
- [`agent.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/agent/src/agent.ts)：状态、事件和生命周期。
- [`session-manager.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/session-manager.ts)：Session 树和 JSONL 记忆。
- [`compaction.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/compaction/compaction.ts)：压缩准备、切点和 summary。
- [`resource-loader.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/resource-loader.ts)：资源和扩展加载。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 课程验收

完整课程测试：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests
```

完成本章后，下一步是把当前 `course.json` 真源接入 Web 生产构建，确保文档、架构图、源码证据和章节状态不会漂移。
