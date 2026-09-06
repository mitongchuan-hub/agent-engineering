# Learn Pi

从 Pi 固定提交学习 Coding Agent 内核的 Python 实验课程。

本项目的主线是 Agent，而不是 CLI：

```text
prompt -> provider -> assistant -> tool -> tool result -> provider
```

## 当前进度

- [建设计划](PLAN.md)
- [完整系统规划](SYSTEMS.md)
- [课程目录](course.json)
- [上游源码证据](UPSTREAM.md)
- [第 01 章：最小 Agent Loop](s01_agent_loop/README.md)
- [第 02 章：Provider 流与 EventStream](s02_provider_stream/README.md)
- [第 03 章：Agent 状态与事件协议](s03_agent_events/README.md)
- [第 04 章：工具契约与参数校验](s04_tool_contract/README.md)
- [第 05 章：并行工具与结果顺序](s05_parallel_tools/README.md)
- [第 06 章：Steering 与 Follow-up 队列](s06_message_queues/README.md)
- [第 07 章：Abort、错误与结束边界](s07_control_boundaries/README.md)
- [第 08 章：上下文转换边界](s08_context_boundary/README.md)
- [第 09 章：Session 记忆与树形历史](s09_session_memory/README.md)
- [第 10 章：压缩、重试与上下文恢复](s10_context_recovery/README.md)
- [第 11 章：扩展工具与资源边界](s11_extension_boundary/README.md)
- [第 12 章：综合 Coding Agent](s12_comprehensive/README.md)
- [第 02 章架构图](s02_provider_stream/architecture.svg)
- [第 01 章代码](s01_agent_loop/code.py)

## 运行

需要共享 Conda 环境 `agent-engineering`：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s01_agent_loop/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests
```

第 01 章完全离线，不需要 API Key。后续章节会逐步加入 Provider 流、事件协议、工具校验、并行执行、队列、Session 和上下文恢复。

## 上游版本

课程事实真源固定为 `agent-source/pi` 的提交 `9767ba275f3e9a5ee0f5c5342249b629ab1b2282`。本机安装版只用于行为核验。
