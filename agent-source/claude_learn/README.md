# claude_learn —— 用 Python 重建 claude-code 的「提示词生态」机制（分步教学）

> 配套源码：`agent-source/claude-code/`（Anthropic 官方仓库：plugins / commands / hooks / examples）
> 说明：claude-code 核心引擎闭源，但它开源的**插件与提示词体系**是公开的天花板样本。
> 这里与 c/d/p 三家对等，用可运行 Python 重建它的五个机制。

## 步骤导航

| 步骤 | 主题 | 对应源码 | 你能掌握 |
|---|---|---|---|
| [x01](x01_plugin_manifest/) | 插件结构 | `plugins/code-review/.claude-plugin/plugin.json` | 插件 = manifest + commands 目录 |
| [x02](x02_allowed_tools/) | allowed-tools 白名单 | `plugins/*/commands/*.md` 的 YAML 头 | 前缀匹配权限引擎 |
| [x03](x03_playbook/) | 多 Agent 剧本 | `plugins/code-review/commands/code-review.md` | 成本分层 + 并行编排 |
| [x04](x04_hooks/) | PreToolUse 钩子 | `examples/hooks/bash_command_validator_example.py` | 命令执行前的拦截 |
| [x05](x05_commands/) | 命令解析器 | `commands/*.md` YAML 头格式 | 提示词即软件的 CLI |
| [x06](x06_comprehensive/) | 综合：迷你插件引擎 | 以上全部 | manifest→白名单→钩子→执行 全链路 |

## 怎么跑

```bash
python agent-source/claude_learn/x01_plugin_manifest/code.py
```