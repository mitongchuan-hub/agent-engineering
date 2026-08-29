# x05: 命令解析器 —— /命令 即能力入口

> claude 源码对照：`.claude/commands/`（commit-push-pr / dedupe / triage-issue 真实样例）
> 上一步：[x04 hooks](../x04_hooks/) ｜ 下一步：[x06 综合引擎](../x06_comprehensive/)

## 问题

用户怎么触发一个剧本？claude 的答案是：**命令**——`/review`、`/commit-push-pr`。
一个 md 文件 = 一个命令 = 一个能力入口。

## 方案

```
commands/triage-issue.md  →  注册 /triage-issue
  ├─ YAML 头：description + allowed-tools（接口规格）
  └─ 正文：多步剧本（执行逻辑）
```

## 原理（读 code.py）

```python
class CommandRegistry:
    def __init__(self, sources):           # md 文件即命令定义
        for name, md in sources.items():
            header = parse_yaml_header(md)  # 解析 YAML 头
            self.parsed.append({name, description, allowed_tools, body})

def invoke(registry, cmd, args=""):         # /review --params
    c = registry.find(cmd.lstrip("/"))      # 加载定义
    # 汇报：权限、正文、交给调度器需求
```

## 运行

```bash
python x05_commands/code.py
# [CLI] 用户输入：/triage-issue --owner=octo/repo --issue=42
#   ✅ 已加载命令 /triage-issue → 描述/权限/正文首行
# 🚫 未知命令 /nope → 提示可用列表
```

## 自测问答

**Q：加一个新命令要改代码吗？**
A：不用。往 commands 目录放一个 md 即注册完成（插件式）。这就是"提示词即软件"的本质：**能力是数据，解释器是通用引擎**。

**Q：YAML 头和传统 CLI 的 --help 有什么关系？**
A：等价物。description = usage 摘要，allowed-tools = 声明它能动什么权限（对应传统命令`capabilities`）。只是"执行体"变成了提示词剧本。

## 延伸

- x01：命令来自插件的 commands 目录（组合关系）
- x06：命令在引擎里被真正"执行"