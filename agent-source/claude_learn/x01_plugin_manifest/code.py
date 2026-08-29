#!/usr/bin/env python3
"""
x01_plugin_manifest.py - claude_learn 第 1 步：插件结构（manifest + commands）

claude-code 的插件由两部分组成（对照真实源码 plugins/code-review/）：
    .claude-plugin/plugin.json   插件元数据（name/description/version/author）
    commands/*.md                命令剧本（带 YAML 头的 Markdown）

这一章重建一个"插件加载器"：解析 manifest + 扫描 commands 目录，
输出插件的能力清单。为 x02（白名单）和 x03（剧本）打地基。

概念（自测点）：
    1. manifest = 插件身份证；commands = 能力清单
    2. YAML 头携带两个关键声明：allowed-tools（权限）、description（用途）
    3. "提示词即软件"：能力边界在 md 里声明，引擎只管加载与执行

Usage:
    python x01_plugin_manifest/code.py
"""

import re
from pathlib import Path
from typing import List

# ① 内置一个真实插件的 manifest（与 claude-code 仓库 plugins/code-review 同款结构）
PLUGIN_MANIFEST = {
    "name": "code-review",
    "description": "Automated code review for pull requests using multiple "
                   "specialized agents with confidence-based scoring",
    "version": "1.0.0",
    "author": {"name": "Boris Cherny", "email": "boris@anthropic.com"},
}


# ② 内置 code-review 的命令剧本（YAML 头简化版，真实结构在其头 5 行）
COMMAND_MD = """
---
allowed-tools: Bash(gh issue view:*), Bash(gh search:*), Bash(gh pr diff:*), mcp__github_inline_comment__create_inline_comment
description: Code review a pull request
---

Provide a code review for the given pull request.

1. Launch a haiku agent to check if the PR is reviewable.
2. Launch 4 agents in parallel to independently review the changes.
"""


# ---------------------------------------------------------------- 解析器

def parse_yaml_header(md: str) -> dict:
    """解析 commands/*.md 的 YAML 头（--- ... --- 之间两行）。"""
    m = re.search(r"^---\n(.*?)^---$", md, re.M | re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class PluginLoader:
    """极简插件加载器：manifest + commands -> 能力清单。"""

    def __init__(self, manifest: dict, commands: List[tuple]):
        self.manifest = manifest
        self.commands = commands  # [(command_name, md_content)]

    def load(self) -> dict:
        parsed = []
        for name, md in self.commands:
            header = parse_yaml_header(md)
            parsed.append({
                "name": name,
                "description": header.get("description", ""),
                "allowed_tools": [t.strip() for t in
                                  header.get("allowed-tools", "").split(",") if t.strip()],
                "body_lines": len([l for l in md.splitlines() if l.strip()]),
            })
        return {
            "plugin": self.manifest["name"],
            "version": self.manifest["version"],
            "author": self.manifest["author"]["name"],
            "summary": self.manifest["description"],
            "commands": parsed,
        }


if __name__ == "__main__":
    print("演示：插件加载器（manifest + commands → 能力清单）\n")
    loader = PluginLoader(PLUGIN_MANIFEST, [("code-review", COMMAND_MD)])
    info = loader.load()

    print(f"插件      : {info['plugin']} v{info['version']}（作者 {info['author']}）")
    print(f"简介      : {info['summary'][:60]}...")
    for c in info["commands"]:
        print(f"\n命令      : {c['name']}")
        print(f"  描述    : {c['description']}")
        print(f"  权限    : {len(c['allowed_tools'])} 条（已解析）")
        for t in c["allowed_tools"]:
            print(f"    - {t}")
        print(f"  正文行数: {c['body_lines']}")

    print("""
[结论] 插件 = 身份证(manifest) + 办事清单(commands)。
       命令的权力边界（allowed-tools）在 YAML 头声明 —— "提示词即软件"的第一层。
       下一步 x02：白名单怎么精确匹配。""")