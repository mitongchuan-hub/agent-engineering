# d02: 插件钩子 —— 改 Agent 行为 = 加插件，不动循环

> deepseek 源码对照：`packages/core/agent-loop`（preStep 里的 dispatch.waterfall）+ `extensions/*`
> 上一步：[d01 状态机](../d01_turn_step_loop/) ｜ 下一步：[d03 Inbox](../d03_inbox/)

## 问题

给 Agent 加"安全审查"或"上下文注入"，最蠢的办法是改循环代码：
循环是主动脉，动一次查一次回归。**能不能把扩展点做成插槽，只插不改？**

## 方案：dispatch.waterfall（水流式插件链）

```
调模型之前（agent/pre-step）：
  插件A(安全审查) → 插件B(上下文注入) → 插件C(审计日志)
       │
       └─ 任一个 block() 就中断 -> 本次 step 取消（不发模型请求）
```

**waterfall 的语义**：前一个插件的处理结果传给后一个——链式、有序、可阻断。
（对比 parallel：并发独立；代码里 sort(key=order) 保证确定性。）

## 原理（读 code.py）

### ① 插件 = 一个方法

```python
class SecurityGuard(Plugin):
    name = "security-guard"
    order = 10                      # 越小越先执行

    def on_pre_step(self, ctx: PluginContext):
        for w in ["删除数据库", "rm -rf"]:
            if w in text: ctx.block(f"检测到敏感操作：{w}")
```

### ② 水流式分发

```python
def waterfall(self, event, ctx):
    for p in sorted(self._plugins, key=order):
        p.on_pre_step(ctx)
        if ctx.blocked: break        # 任何插件喊停，链终止
```

### ③ 一个钩子点，三种用法

| 插件 | 做什么 | 类型 |
|---|---|---|
| SecurityGuard | 检测敏感词→block | 拦截 |
| ContextInjector | 追加工作目录信息 | 改写 |
| LoggingPlugin | 打日志不改数据 | 审计 |

## 运行

```bash
python d02_plugin_hooks/code.py
# [任务] 帮我写个二分查找 → ✅ 放行（消息 +1：注入信息）
# [任务] 删除数据库并清空日志 → ❌ 被 检测到敏感操作：删除数据库 阻断
```

## 自测问答

**Q："一切皆插件"到底指什么？**
A：循环的每个环节（pre-step、tool-call、post-step…）都是钩子点，能力以插件形式挂载：工具、subagent、webhook、评测全是插件。改需求=换插件，不换代。

**Q：waterfall 和 event（发布订阅）区别？**
A：waterfall 有**返回链**——前一个的结果是后一个的输入，还能阻断后继；事件总线是广播（谁订阅谁收到），无链式依赖。deepseek 两种都有：waterfall（决策链）、serial（有序事件）。

**Q：插件执行顺序怎么保证？**
A：显式 order 字段排序（代码里 sort）。顺序重要时（先审查后注入）必须可配置，不能依赖注册顺序。

## 延伸

- d01：钩子点就是状态机里的 pre-step 位置
- 对比 codex_learn c03 审批：那是"内置的决策层"；deepseek 是"任意行为的插槽"