#!/usr/bin/env python3
"""
x02_allowed_tools.py - claude_learn 第 2 步：allowed-tools 白名单引擎

claude-code 命令用 YAML 头声明自己能用的工具（真实样例）：
    allowed-tools: Bash(gh issue view:*), Bash(gh search:*),
                   mcp__github_inline_comment__create_inline_comment
含义：
    Bash(gh pr view:*)  → 允许执行 bash 命令，且命令前缀匹配 "gh pr view"
    mcp__server__tool   → 允许调用 MCP 服务器上的特定工具
    不在白名单          → 模型不能用（权限最小化）

本章重建解析 + 匹配引擎（可运行演示）。

自测点：
    1. Bash 规则 = 程序名 + 参数前缀（前缀通配 *）
    2. mcp__server__tool 三段式命名 → 精确匹配
    3. deny by default：白名单之外一律拦截（正例白名单而非黑名单）

Usage:
    python x02_allowed_tools/code.py
"""

import re
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------- 规则模型

@dataclass
class BashRule:
    arg_prefix: str          # 例如 gh pr view （per 命令前缀）
    arg_glob: bool = True    # 是否允许任意后缀（:* 通配）

    def matches(self, command: str) -> bool:
        if self.arg_glob:
            return command.startswith(self.arg_prefix)
        return command == self.arg_prefix


@dataclass
class McpRule:
    tool_name: str           # 例如 github_inline_comment/create_inline_comment

    def matches(self, tool: str) -> bool:
        return tool == self.tool_name


@dataclass
class Policy:
    bash: List[BashRule] = field(default_factory=list)
    mcp: List[McpRule] = field(default_factory=list)
    allowed_plain: set = field(default_factory=set)   # 无参数执行的完整命令


# ---------------------------------------------------------------- 解析

def parse_allowed_tools(line: str) -> Policy:
    """把 "Bash(gh pr view:*), mcp__x__y" 解析成规则集。"""
    policy = Policy()
    for item in line.split(","):
        item = item.strip()
        if item.startswith("Bash(") and item.endswith(")"):
            inner = item[5:-1]
            if inner.endswith(":*"):
                policy.bash.append(BashRule(inner[:-2], True))
            else:
                policy.bash.append(BashRule(inner, False))
        elif item.startswith("mcp__"):
            policy.mcp.append(McpRule(item[5:]))   # 去 mcp__ 前缀，保留 server__tool
        elif item:
            policy.allowed_plain.add(item)
    return policy


# ---------------------------------------------------------------- 匹配

def check(policy: Policy, kind: str, value: str) -> tuple:
    """返回 (允许?, 命中规则)。deny by default。"""
    if kind == "bash":
        for r in policy.bash:
            if r.matches(value):
                return True, f"Bash(前缀 {r.arg_prefix}:*)"
        return False, "不在 Bash 白名单"
    if kind == "mcp":
        for r in policy.mcp:
            if r.matches(value):
                return True, f"mcp__{value}"
        return False, "不在 MCP 白名单"
    if value in policy.allowed_plain:
        return True, f"plain {value}"
    return False, "不在白名单"


if __name__ == "__main__":
    # 真实样例（取自 claude-code 仓库 code-review 插件）
    RAW = ("Bash(gh issue view:*), Bash(gh search:*), Bash(gh pr diff:*), "
           "Bash(gh pr view:*), Bash(gh pr list:*), "
           "mcp__github_inline_comment__create_inline_comment")
    policy = parse_allowed_tools(RAW)

    print(f"白名单解析结果（共 {len(policy.bash)} 条 Bash + {len(policy.mcp)} 条 MCP）\n")
    cases = [
        ("bash", "gh pr view 123",                    "✅ 命中前缀"),
        ("bash", "gh issue view 5",                   "✅ 另一个前缀"),
        ("bash", "gh label create x",                 "❌ 不在名单"),
        ("bash", "rm -rf /",                          "❌ 完全无关"),
        ("mcp",  "github_inline_comment/create_inline_comment", "✅ 精确匹配"),
        ("mcp",  "github_inline_comment/delete_comment",       "❌ 非白名单工具"),
    ]
    for kind, value, expect in cases:
        ok, hit = check(policy, kind, value)
        print(f"  {'✅' if ok else '🚫'} [{kind:4}] {value[:44]:44} -> {hit}")

    print("""
[结论] allowed-tools 的精髓是"默认拒绝"：
       模型能用什么，由命令的 YAML 头显式声明 —— 权限最小化。
       对比 codex 的 approvals（决策时审批），这里是"声明式边界"（执行前就锁死）。""")