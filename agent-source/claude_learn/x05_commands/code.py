#!/usr/bin/env python3
"""
x05_commands.py - claude_learn 第 5 步：命令解析器（提示词即软件的 CLI）

claude-code 的 commands/*.md 是"能力入口"：YAML 头声明元信息，正文是剧本。
本章做一个命令行工具：/review 这样的命令 → 读取对应 md → 解析 YAML 头 →
吐出可以交给引擎执行的结构（命令名、描述、allowed-tools、正文）。

自测点：
    1. YAML 头 = 命令的"命令行参数表"，正文 = 执行逻辑（但用自然语言）
    2. 命令注册：扫描 commands 目录即可新增能力（插件式）
    3. "提示词即软件"第三层：能力是数据，引擎是解释器

Usage:
    python x05_commands/code.py
"""

import re
from pathlib import Path
from typing import List

# 用真实的 claude 内置命令样例（从 .claude/commands 提炼的头部）
COMMANDS_MD: dict = {
    "triage-issue": """---
allowed-tools: Bash(gh issue view:*), Bash(gh pr list:*)
description: Triage a GitHub issue: classify, label, and route
---

1. Launch a haiku agent to classify the issue by area.
2. Launch a sonnet agent to suggest labels and a fix approach.
""",
    "commit-push-pr": """---
allowed-tools: Bash(git status), Bash(git add:*), Bash(git commit:*), Bash(gh pr create:*)
description: Commit changes, push, and open a PR
---

1. Inspect the current diff.
2. Suggest a commit message, then commit, push, and open a PR.
""",
}


# ---------------------------------------------------------------- 解析器

def parse_yaml_header(md: str) -> dict:
    m = re.search(r"^---\n(.*?)^---$", md, re.M | re.S)
    out = {}
    if m:
        for line in m.group(1).strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


class CommandRegistry:
    """命令注册表：md 文件即命令定义。"""

    def __init__(self, sources: dict):
        self.parsed: List[dict] = []
        for name, md in sources.items():
            header = parse_yaml_header(md)
            self.parsed.append({
                "name": name,
                "description": header.get("description", ""),
                "allowed_tools": [t.strip() for t in
                                  header.get("allowed-tools", "").split(",") if t.strip()],
                "body": md.split("---", 2)[-1].strip(),
            })

    def find(self, name: str) -> dict:
        for c in self.parsed:
            if c["name"] == name:
                return c
        raise KeyError(name)

    def list(self) -> List[str]:
        return [c["name"] for c in self.parsed]


# ---------------------------------------------------------------- 演示：/review 式调用

def invoke(registry: CommandRegistry, cmd: str, args: str = "") -> None:
    """模拟 CLI：/命令 [参数] → 加载定义 → 汇报将干什么。"""
    name = cmd.lstrip("/")
    print(f"[CLI] 用户输入：/{name} {args}")
    try:
        c = registry.find(name)
    except KeyError:
        print(f"  ❌ 未知命令 /{name}，可用：{registry.list()}\n")
        return
    print(f"  ✅ 已加载命令 /{name}")
    print(f"    描述   : {c['description'][:48]}")
    print(f"    权限   : {len(c['allowed_tools'])} 条")
    print(f"    正文   : {c['body'].splitlines()[0][:40]}…")
    print(f"    （正文即剧本：交给 x03 的调度器执行 {args or '（无参数）'}）\n")


if __name__ == "__main__":
    print("演示：命令解析器（/命令 即能力入口）\n")
    reg = CommandRegistry(COMMANDS_MD)
    print(f"已注册命令：{reg.list()}\n")
    invoke(reg, "/triage-issue", "--owner=octo/repo --issue=42")
    invoke(reg, "/commit-push-pr")
    invoke(reg, "/nope")

    print("[结论] 加能力 = 放一个 md 进 commands 目录：注册自动完成。")
    print("       YAML 头是'接口规格'，正文是'执行逻辑'——提示词与工程在这里统一。")