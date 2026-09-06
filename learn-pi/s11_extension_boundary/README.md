# 第 11 章：扩展与资源边界

## 本章问题

一个 Coding Agent 不应该把所有能力都写进核心 Loop。Pi 通过资源加载器和扩展 API，把工具、技能、提示模板、主题和项目上下文接入运行时。

```text
Extension factory
  -> ExtensionAPI.registerTool / on()
  -> session_start
  -> resources_discover
  -> ResourceLoader.extendResources
  -> Agent Runtime
```

## 源码调用链

```text
DefaultResourceLoader.reload()
  -> resolve package/resource paths
  -> load extensions
  -> load skills / prompt templates / themes
  -> load AGENTS.md / CLAUDE.md

AgentSession.bindExtensions()
  -> extensionRunner.emit(session_start)
  -> emitResourcesDiscover()
  -> resourceLoader.extendResources()
```

扩展发现资源时，不直接修改 Agent Loop，而是返回路径；Session 再把路径交给 `ResourceLoader`。这是扩展边界的核心。

## 最小实现

本章的 `ExtensionAPI` 只暴露四个教学动作：

- `register_tool()`：向工具池添加 LLM 可调用工具。
- `register_command()`：注册命令元数据。
- `on("session_start", ...)`：在 Session 启动时初始化。
- `on("resources_discover", ...)`：提供额外 skill/prompt/theme 路径。

`ResourceLoader.reload()` 每次建立新的快照，收集资源和诊断。扩展抛错、主题 JSON 损坏、资源路径缺失都不会让其他资源完全失效。

## 资源类型

| 资源 | 本章处理 | 运行时用途 |
|---|---|---|
| Skill | Markdown frontmatter + body | 按需加载的工作流知识 |
| Prompt template | Markdown/text | 用户可调用的提示模板 |
| Theme | JSON 对象 | 交互界面主题配置 |
| Context file | `AGENTS.override.md`、`AGENTS.md`、`CLAUDE.md` | 项目级上下文 |
| Extension | Python factory 教学投影 | 工具、命令和资源发现 hook |

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s11_extension_boundary/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s11_extension_boundary.py
```

示例会创建临时教学资源并加载一个扩展工具。代码默认只在 `.task-output/s11-demo` 下写入示例文件。

## 关键测试

- 扩展可以注册工具、命令和生命周期 handler。
- loader 发现 skills、prompt、theme 和上下文文件。
- `resources_discover` 返回的资源路径会被再次加载。
- `no_*` 开关关闭自动发现，但显式路径仍然有效。
- 缺失/损坏资源产生诊断，不阻塞整体加载。
- 一个扩展失败不影响其他扩展。
- 工具名冲突会报告诊断并保留加载顺序。
- reload 重建快照，不累积旧注册结果。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| Python factory | TypeScript/JavaScript extension module |
| 只实现资源类和少数事件 | Pi 的 ExtensionAPI 还支持大量 Agent、Session、UI 和 Provider 事件 |
| 资源路径用简化目录扫描 | Pi 结合 package manager、作用域、metadata 和 glob 规则 |
| 主题只校验 JSON 对象 | Pi 有完整主题 schema 和交互主题加载器 |
| 工具只保存 name/description/execute | Pi 工具包含 TypeBox schema、渲染器、更新和执行策略 |
| 诊断留在快照 | Pi 还通过 extension runner 和 UI/reporting 分发诊断 |

权限确认、MCP transport 和产品模式不在这里伪造；只有固定提交有证据的扩展接口才进入课程。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`resource-loader.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/resource-loader.ts)：`DefaultResourceLoader`、项目上下文发现、资源 reload 和 `extendResources`。
- [`messages.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/messages.ts)：资源/扩展消息进入 LLM context 的转换边界。
- [`extensions/types.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/extensions/types.ts)：`ExtensionAPI`、`ToolDefinition`、`resources_discover` 和扩展事件类型。
- [`extensions/runner.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/extensions/runner.ts)：`emitResourcesDiscover` 的逐扩展调用和错误隔离。
- [`dynamic-tools.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/examples/extensions/dynamic-tools.ts)：动态注册工具的公开示例。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 12 章把 Agent Loop、工具、上下文、Session、恢复和扩展组合成完整的离线 Coding Agent。
