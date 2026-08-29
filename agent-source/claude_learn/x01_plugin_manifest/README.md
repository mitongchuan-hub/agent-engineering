# x01: 插件结构 —— manifest + commands

> claude 源码对照：`plugins/code-review/`（.claude-plugin/plugin.json + commands/）
> 上一步：无（claude_learn 第一课）｜ 下一步：[x02 allowed-tools](../x02_allowed_tools/)

## 问题

"一切能力来自插件"——那插件长什么样？答案：**两件套**。

## 方案

```
插件目录/
├── .claude-plugin/plugin.json     ← 身份证（name/description/version/author）
└── commands/*.md                  ← 办事清单（YAML 头 + 提示词剧本）
```

## 原理（读 code.py）

```python
PLUGIN_MANIFEST = {
    "name": "code-review",
    "description": "Automated code review for pull requests...",
    "version": "1.0.0",
    "author": {"name": "Boris Cherny", ...},      # ← 真实样例
}
```

```python
def parse_yaml_header(md):
    # --- ... --- 之间 = YAML 头：allowed-tools / description
    # 正文 = 多步剧本（交给 x03 调度）
```
命令的**权力边界**（allowed-tools）声明在 YAML 头——
这是"提示词即软件"的第一层：能力用数据描述，引擎只负责加载。

## 运行

```bash
python x01_plugin_manifest/code.py
# 插件: code-review v1.0.0 → 命令/权限/正文行数 全部解析输出
```

## 自测问答

**Q：为什么 manifest 和 commands 分离？**
A：manifest 给"市场/管理"用（列表、版本、作者），commands 给"执行引擎"用（怎么跑）。关注点分离，也让插件可以被索引和分发。

**Q：commands 的 YAML 头是什么？**
A：命令的"接口规格"——description（干什么）、allowed-tools（能用什么工具）。正文是执行逻辑（自然语言剧本）。接口与实现分离，和传统软件一致，只是"实现"变成了提示词。

## 延伸

- x05：command 作为 CLI 能力入口（/命令）
- x06：插件引擎把这一层串起来