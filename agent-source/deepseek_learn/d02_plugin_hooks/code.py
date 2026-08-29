#!/usr/bin/env python3
"""
d02_plugin_hooks.py - deepseek_learn 第 2 步：插件钩子（waterfall 水流式改写）

deepseek-harness 的灵魂："Everything is a Plugin"。
实现内核：dispatch.waterfall("agent/pre-step", ...)——
在每次"调模型之前"跑一串插件链，插件可以：
    拦截（拒绝本次 step）、改写消息（注入/删除）、追加上下文。

对应源码：packages/core/agent-loop（preStep 里的 dispatch.waterfall）+ extensions/*

本步重建：Plugin 注册表 + waterfall 链（前一个插件的输出 = 后一个插件的输入）。

面试点：
    1. 钩子 = 不改循环就能改行为（安全审查/参数修正/租户隔离都是插件）
    2. waterfall 与 parallel 的区别：链式依赖 vs 独立并发
    3. 阻断 = 插件返回 reject，事件不再继续

Usage:
    python d02_plugin_hooks/code.py
"""

from typing import List, Optional


class PluginContext:
    """传给插件链的上下文：消息 + 元数据，插件可改写。"""

    def __init__(self, messages: List[dict], turn: int, step: int):
        self.messages = messages
        self.turn, self.step = turn, step
        self.blocked = False
        self.block_reason: Optional[str] = None

    def block(self, reason: str):
        self.blocked = True
        self.block_reason = reason


# ---------------------------------------------------------------- 插件基类

class Plugin:
    name = "base"
    order = 100  # 越小越先跑

    def on_pre_step(self, ctx: PluginContext) -> None:
        """在模型调用前被调用。子类覆盖。"""
        raise NotImplementedError


# ---------------------------------------------------------------- 示例插件

class SecurityGuard(Plugin):
    """安全审查：消息里含敏感词则阻断。"""

    name = "security-guard"
    order = 10

    SENSITIVE = ["删除数据库", "rm -rf"]

    def on_pre_step(self, ctx: PluginContext):
        for m in ctx.messages:
            text = m.get("content") or ""
            for w in self.SENSITIVE:
                if w in text:
                    ctx.block(f"检测到敏感操作：{w}")


class ContextInjector(Plugin):
    """注入上下文：给每轮都塞一条"当前工作目录"等信息。"""

    name = "context-injector"
    order = 20

    def on_pre_step(self, ctx: PluginContext):
        ctx.messages.append({"role": "user",
                             "content": "(插件注入) 当前工作目录：/home/user/project"})


class LoggingPlugin(Plugin):
    """审计日志：记录每步，不修改。"""

    name = "logging"
    order = 100

    def on_pre_step(self, ctx: PluginContext):
        print(f"    [hook:{self.name}] turn={ctx.turn} step={ctx.step} "
              f"消息数={len(ctx.messages)}")
        if ctx.messages and ctx.messages[-1].get("content", "").startswith("(插件注入)"):
            print(f"    [hook:{self.name}] 检测到注入消息 ✓")


# ---------------------------------------------------------------- Dispatcher（waterfall）

class Dispatcher:
    """waterfall：按 order 排序，串行执行插件链（前一个的结果传后一个）。"""

    def __init__(self):
        self._plugins: List[Plugin] = []

    def use(self, p: Plugin):
        self._plugins.append(p)
        self._plugins.sort(key=lambda p: p.order)
        return self

    def waterfall(self, event: str, ctx: PluginContext) -> PluginContext:
        """水流式：按 order 依次执行；任一个 block() 则中断、拒绝。"""
        print(f"  [dispatch] waterfall('{event}') 开始，插件链："
              f"{[p.name for p in self._plugins]}")
        for p in self._plugins:
            p.on_pre_step(ctx)
            if ctx.blocked:
                print(f"  [dispatch] 链中断于 {p.name}：{ctx.block_reason}")
                break
        return ctx


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：插件钩子（pre-step 拦截/改写/审计）\n")

    dispatcher = Dispatcher()
    dispatcher.use(SecurityGuard()).use(ContextInjector()).use(LoggingPlugin())

    for task in ["帮我写个二分查找", "删除数据库并清空日志"]:
        ctx = PluginContext(messages=[{"role": "user", "content": task}], turn=1, step=1)
        print(f"[任务] {task}")
        dispatcher.waterfall("agent/pre-step", ctx)
        if ctx.blocked:
            print(f"[结果] ❌ 被 {ctx.block_reason} 阻断，本次 step 不调模型\n")
        else:
            n = len(ctx.messages)
            print(f"[结果] ✅ 放行，消息条数 {n}，最后一条：{ctx.messages[-1]['content'][:30]}...\n")

    print("""
[结论] waterfall 钩子的威力：改 Agent 行为 = 加插件，不动循环。
       生产场景：安全审查（SecurityGuard）、参数修正、多租户上下文注入
       都是同一个钩子点。deepseek 的 cordis 框架把整套做成基础设施。""")