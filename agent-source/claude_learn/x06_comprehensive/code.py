#!/usr/bin/env python3
"""
x06_comprehensive.py - claude_learn 第 6 步：综合——迷你插件引擎

把 x01~x05 串成一条完整的"提示词即软件"流水线：

    manifest（x01）→ allowed-tools（x02）→ 剧本调度（x03）→ 钩子拦截（x04）→ 命令入口（x05）

本步实现一个"迷你插件引擎"：加载一个插件 → 执行它的命令 →
每个工具调用都过白名单 + 钩子 → 输出审计日志。

自测点：
    1. 插件引擎 = 加载器 + 权限层 + 执行层 + 钩子层（四层职责分离）
    2. deny by default：任何工具调用先过白名单再看钩子
    3. 审计日志贯穿全链路（可观测）

Usage:
    python x06_comprehensive/code.py
"""

import re

# ---------------------------------------------------------------- 插件定义（data）

PLUGIN = {
    "name": "review-bot",
    "version": "1.0.0",
    "commands": {
        "review": {
            "allowed_tools": "Bash(gh pr view:*), Bash(gh pr diff:*), mcp__report__writemarkdown",
            "playbook": "haiku: 检查 PR 是否可评审\nsonnet: 分析 diff 并给出问题清单",
        }
    },
}


# ---------------------------------------------------------------- 各层（复用 x01-x05 的精简版）

def parse_allowed(line: str) -> list:
    out = []
    for item in line.split(","):
        item = item.strip()
        if item.startswith("Bash("):
            out.append(("bash", item[5:-1].removesuffix(":*")))
        elif item.startswith("mcp__"):
            out.append(("mcp", item[5:]))
    return out


class Engine:
    def __init__(self, plugin: dict):
        self.plugin = plugin
        self.log: list = []

    def _authz(self, command: dict) -> bool:
        """权限层：allowed-tools 白名单（deny by default）。"""
        rules = parse_allowed(
            self.plugin["commands"][command["cmd"]]["allowed_tools"])
        for kind, name in rules:
            if kind == "bash" and command["tool"] == "Bash" \
               and command["arg"].startswith(name):
                return True
            if kind == "mcp" and command["tool"] == "mcp__" + name:
                return True
        return False

    def _hook(self, command: dict) -> str:
        """钩子层：危险命令拦截。"""
        if command["tool"] == "Bash" and command["arg"].startswith("rm -rf /"):
            return "deny"
        return "allow"

    def run(self, cmd_name: str, script: list) -> None:
        """执行层：逐个命令走 白名单 → 钩子 → 执行（模拟）。"""
        print(f"▶ 执行插件 {self.plugin['name']} 的命令 /{cmd_name}\n")
        for step in script:
            tool, arg = step["tool"], step["arg"]
            command = {"cmd": cmd_name, "tool": tool, "arg": arg}
            self.log.append({"step": str(step), "authz": None, "hook": None})

            # ① 白名单
            if not self._authz(command):
                self.log[-1]["authz"] = False
                print(f"  🚫 [权限] {tool}({arg[:30]}) 不在白名单 → 拒绝")
                continue
            self.log[-1]["authz"] = True
            # ② 钩子
            h = self._hook(command)
            self.log[-1]["hook"] = h
            if h == "deny":
                print(f"  🚫 [钩子] {tool}({arg[:30]}) 被钩子拦截")
                continue
            # ③ 执行（模拟）
            print(f"  ✅ {tool}({arg[:30]}) → 执行成功")
        print()


if __name__ == "__main__":
    print("演示：迷你插件引擎（提示词即软件 全链路）\n")
    eng = Engine(PLUGIN)

    # 剧本执行：模拟 tool 调用序列
    eng.run("review", [
        {"tool": "Bash", "arg": "gh pr view 42"},            # ✅ 白名单 + 钩子放行
        {"tool": "Bash", "arg": "gh pr diff 42"},            # ✅
        {"tool": "Bash", "arg": "cat /etc/passwd"},          # 🚫 白名单外
        {"tool": "mcp__report__writemarkdown", "arg": "out.md"},  # ✅ MCP 工具
        {"tool": "Bash", "arg": "rm -rf /tmp"},              # 🚫 钩子拦截（改前缀成 rm -rf / 才会命中，此处演示路径级别）
    ])

    print("\n审计日志（全链路可观测）：")
    for e in eng.log:
        s = e["step"].replace('{"tool": "', "").replace('", "arg": "', " ")
        print(f"  {s[:46]:46} authz={e['authz']} hook={e['hook']}")

    print("""
[结论] 引擎四层 = 提示词即软件的完整答案：
       加载（manifest/commands）→ 授权（allowed-tools）→ 拦截（hooks）→ 执行。
       ×01~×05 的每一层都能在这张图里找到位置。claude 系列结束！""")