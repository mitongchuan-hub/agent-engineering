# x04: Hooks —— 执行瞬间的拦截与改写

> claude 源码对照：`examples/hooks/bash_command_validator_example.py`（真实 Python 钩子）
> 上一步：[x03 多 Agent 剧本](../x03_playbook/) ｜ 下一步：[x05 命令解析器](../x05_commands/)

## 问题

allowed-tools 是"声明式边界"，但有些事只能**执行瞬间**判断：
这条命令今天不能跑、这个仓库路径要特殊处理、这条 grep 可以优化成 rg。

## 方案：事件钩子

```
工具调用 ──▶ PreToolUse 钩子链 ──▶ 放行/改写/拒绝/询问 ──▶ 执行
```

## 原理（读 code.py）

```python
def validator_hook(evt):            # 参考真实 bash_command_validator 示例
    if evt.command.startswith("grep "):
        return HookDecision("edit", "更快的替代", evt.command.replace("grep ", "rg "))  # 改写
    if evt.command.startswith("rm -rf /"):
        return HookDecision("deny", "危险命令")                                          # 拒绝
    return HookDecision("allow")                                                          # 放行

def run_hooks(hooks, evt):          # deny 优先于 edit/allow；多钩子按注册序
    ...
```

## 运行

```bash
python x04_hooks/code.py
# ✏️ grep -r 'TODO' src  -> [edit] 执行：rg -r 'TODO' src
# 🚫 rm -rf / 重要目录     -> [deny] 危险命令
# ✅ git status           -> [allow]
```

## 自测问答

**Q：钩子决策有哪几种？**
A：allow / deny / ask（问用户）/ edit（改写后执行）。真实 claude hooks 支持全部四种；`ask` 就是"过程式审批"，与 codex approvals 同思想。

**Q：白名单和钩子谁先跑？**
A：先白名单（静态边界，成本低），再钩子（动态决策）。本章 x06 引擎里顺序：authz → hook → 执行。

**Q：钩子能审计吗？**
A：能。在执行前后各挂一道（Pre/PostToolUse），Post 记录结果——全链路可观测（x06 的审计日志就是这么来的）。

## 延伸

- x06：引擎集成 authz + hook + audit
- 对照 deepseek_learn d02（waterfall 插件链）——两者都是"钩子"，一个在工具层（claude）、一个在循环层（deepseek）