#!/usr/bin/env python3
"""
x04_hooks.py - claude_learn 第 4 步：PreToolUse 钩子（命令执行前拦截）

claude-code 的 hooks 机制（examples/hooks/bash_command_validator_example.py 是
真实 Python 实现）：工具执行前/后可以挂脚本钩子，拦截或改写命令。

自测点：
    1. 钩子事件：PreToolUse（执行前）/ PostToolUse（执行后）
    2. 决策：allow（放行）/ deny（拒绝）/ ask（询问）/ edit（改写命令）
    3. 钩子与 allowed-tools 的分工：白名单是"声明式边界"，钩子是"过程式拦截"

Usage:
    python x04_hooks/code.py
"""

import time
from dataclasses import dataclass, field
from typing import Callable, List


# ---------------------------------------------------------------- 钩子协议

@dataclass
class ToolUseEvent:
    tool_name: str
    command: str          # bash 命令
    ts: float = field(default_factory=time.time)


@dataclass
class HookDecision:
    action: str           # allow / deny / ask / edit
    message: str = ""
    edited_command: str = ""


# ---------------------------------------------------------------- 钩子实现（参考真实示例）

def validator_hook(evt: ToolUseEvent) -> HookDecision:
    """参考 claude 的 bash_command_validator：拦截危险命令、改写低效命令。"""
    cmd = evt.command
    # ① 改写：grep 换 rg（真实示例即这么做）
    if cmd.startswith("grep "):
        return HookDecision("edit", "更快的替代", cmd.replace("grep ", "rg ", 1))
    # ② deny：危险命令
    for bad in ("rm -rf /", "mkfs", "dd if="):
        if cmd.startswith(bad):
            return HookDecision("deny", f"危险命令：{bad}")
    # ③ allow：其余放行
    return HookDecision("allow", "符合策略")


def audit_hook(evt: ToolUseEvent) -> HookDecision:
    """第二个钩子：纯记录（演示多钩子串联 + 审计，不拦截）。"""
    print(f"    [audit] {evt.tool_name} @ {time.strftime('%H:%M:%S')} -> {evt.command[:30]}")
    return HookDecision("allow")


# ---------------------------------------------------------------- 钩子链执行器

def run_hooks(hooks: List[Callable], evt: ToolUseEvent) -> HookDecision:
    """按注册顺序执行；deny 优先于 edit/allow（过程式拦截）。"""
    final = HookDecision("allow")
    for hook in hooks:
        d = hook(evt)
        if d.action == "deny":
            return d
        if d.action == "edit":
            final = d                                   # 记录最后一次改写
    return final


if __name__ == "__main__":
    print("演示：PreToolUse 钩子链（validator + audit）\n")
    hooks = [audit_hook, validator_hook]

    commands = [
        "grep -r 'TODO' src",      # edit：grep → rg
        "rm -rf / 重要目录",       # deny
        "git status",              # allow
        "rm -rf /tmp/x",           # 注意：rm -rf / 才拦，这里放行（前缀规则演示）
    ]
    for cmd in commands:
        decision = run_hooks(hooks, ToolUseEvent("Bash", cmd))
        shown = decision.edited_command or cmd
        mark = {"allow": "✅", "deny": "🚫", "edit": "✏️"}[decision.action]
        print(f" {mark} {cmd[:28]:28} -> [{decision.action}] {decision.message}"
              + (f"（执行：{shown[:30]}）" if decision.action == "edit" else ""))

    print("""
[结论] 钩子 vs 白名单（分工）：
       allowed-tools（x02）= 声明式边界：命令能碰什么，静态写死
       hooks = 过程式拦截：执行瞬间还能改/拦/审
       生产里 hook 里还能问用户（action=ask）—— 和 codex 的 approvals 异曲同工。""")