# deepseek_learn —— 用 Python 重建 deepseek-harness 的核心机制（分步教学）

> 配套源码：`agent-source/deepseek-harness/`（TypeScript，60+ 包）
> 教学方式：每步一个可运行 Python 文件，重建其关键设计。
> 核心气质：**一切皆插件**（cordis 框架）——循环、钩子、Inbox 全部可为插件改写。

## 步骤导航

| 步骤 | 主题 | 对应源码包 | 你能掌握 |
|---|---|---|---|
| [d01](d01_turn_step_loop/) | turn/step 状态机 | `core/agent-loop` | 显式状态循环 vs 双层 while |
| [d02](d02_plugin_hooks/) | 插件钩子（waterfall） | `core/agent-loop` + `extensions/*` | 调模型前的拦截/改写点 |
| [d03](d03_inbox/) | Inbox 消息领取 | `core/agent-loop` inbox | 并发唤醒、next-turn/next-step |
| d04 | 严格工具 schema | `core/tools` | ptc/py-types 多维类型推导 |
| d05 | 子 Agent 体系 | `subagent/*` | 进程内/兼容协议的子代理 |
| d06 | 上下文裁剪压缩 | `compaction/*` | 工具结果裁剪 + 分节组装 |
| d07 | 系统提示词组装 | `core/system-prompt` | 分节渲染 + tool-order |

## 怎么跑

```bash
python agent-source/deepseek_learn/d01_turn_step_loop/code.py
```