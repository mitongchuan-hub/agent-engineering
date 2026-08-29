# pi_learn —— 用 Python 重建 pi 的核心机制（分步教学）

> 配套源码：`agent-source/pi/`（TypeScript，10 包）
> 教学方式：每步一个可运行 Python 文件，重建 pi 的关键设计。
> pi 的气质：**事件流驱动 + 模型无关 + 轻量现代**——最适合读源码的第一站。

## 步骤导航

| 步骤 | 主题 | 对应源码 | 你能掌握 |
|---|---|---|---|
| [p01](p01_event_stream/) | 事件流 | `agent/src/agent-loop.ts` | Agent 的全过程变成事件（可观测） |
| [p02](p02_steering/) | steering 消息 | `agent-loop.ts` 外层循环 | 用户中途插话不丢 |
| [p03](p03_parallel_tools/) | 并行工具+事件 | `types.ts` ToolExecutionMode | 两阶段并发 + 双轨事件 |
| p04 | 失败进流 | `types.ts` StreamFn 契约 | 错误编码进流而非抛异常 |
| p05 | provider 层 | `ai/src/providers/` | 40 家模型的统一抽象 |
| p06 | 分支压缩 | `harness/compaction/` | 分支摘要、主线索保留 |
| p07 | JSONL 会话 | `harness/session/jsonl/` | 带 codec 版本化的会话存档 |

## 怎么跑

```bash
python agent-source/pi_learn/p01_event_stream/code.py
```