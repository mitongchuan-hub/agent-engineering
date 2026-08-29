#!/usr/bin/env python3
"""
d07_system_prompt.py - deepseek_learn 第 7 步：系统提示词组装

真正生产级的系统提示词不是一大段静态文本，而是**动态组装**：
deepseek 的 core/system-prompt 包 + renderContextSections——
把提示词拆成"节"（sections），按场景拼装，还带 tool-order（工具排序策略）。

本步重建：
    ① 分节：身份节 / 工具节 / 记忆节 / 任务节
    ② 组装器：按上下文条件启停各节 + 排序
    ③ tool-order：决定模型先看到哪些工具（重要工具排前面省 token）

面试点：
    1. 提示词 = 配置化装配，不是手写一坨
    2. 节可增删（调试/评测时只改一节）
    3. 工具顺序影响模型选择（首因效应对工具选择真实存在）

Usage:
    python d07_system_prompt/code.py
"""

from typing import List


# ---------------------------------------------------------------- 提示词节

class Section:
    """一个提示词节：有名字、内容、启用条件。"""

    def __init__(self, name: str, content: str, enabled: bool = True,
                 order: int = 100):
        self.name = name
        self.content = content
        self.enabled = enabled
        self.order = order   # 越小越靠前（组装顺序）

    def render(self) -> str:
        return f"## {self.name}\n{self.content}"


# ---------------------------------------------------------------- 组装器

class PromptAssembler:
    """按 order 排序、按条件启停地组装 sections（对应 renderContextSections）。"""

    def __init__(self):
        self.sections: List[Section] = []

    def add(self, s: Section) -> "PromptAssembler":
        self.sections.append(s)
        return self

    def assemble(self, task: str) -> str:
        ordered = sorted((s for s in self.sections if s.enabled),
                         key=lambda s: s.order)
        body = "\n\n".join(s.render() for s in ordered)
        return f"{body}\n\n## 任务\n{task}"


# ---------------------------------------------------------------- tool-order（工具排序）

def tool_order_strategy(tool_names: List[str], important_first: List[str]) -> List[str]:
    """重要工具前置：减少模型在工具列表里"挣扎"的 token 与概率偏差。"""
    important = [t for t in tool_names if t in important_first]
    rest = [t for t in tool_names if t not in important_first]
    return important + rest


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：分节组装 + 工具排序策略\n")

    assembler = PromptAssembler()
    assembler.add(Section("identity", "你是资深 HR 招聘顾问，擅长简历与岗位匹配评价。", order=10))
    assembler.add(Section("rules",
                          "铁律：所有分数、技能必须来自工具的**真实返回**，禁止编造。",
                          order=20))
    assembler.add(Section("tools_guide",
                          "工具：compute_match（打分）/ read_text_file（读文件）/ write_file（写报告）",
                          order=30))
    assembler.add(Section("memory",
                          "记忆：候选人是张三，硕士，3 年经验，主攻 Python 后端。",
                          enabled=True, order=25))   # 记忆节插在规则后
    assembler.add(Section("legacy",
                          "（旧功能描述，本次任务不需要）",
                          enabled=False, order=50))  # 禁用节：不渲染

    print("组装结果（已按 order 排序、禁用节剔除）：\n")
    print(assembler.assemble("评估张三对 AI 应用工程师岗的匹配度"))
    print("." * 60)

    # 工具排序
    tools = ["write_file", "read_text_file", "list_files", "compute_match", "search"]
    ordered = tool_order_strategy(tools, important_first=["compute_match", "list_files"])
    print("\ntool-order 策略演示：")
    print(f"  原始：{tools}")
    print(f"  排序：{ordered}（compute_match/list_files 前置）")

    print("""
[结论] 系统提示词的工程化：
       1. 分节组装 → 可配置、可测试、可按场景启停（对照"一坨静态长文"）
       2. 记忆/任务/工具分节 → 后续替换任何一节都不动其他部分
       3. tool-order → 工具顺序影响模型首轮选择，重要工具前置省 token 少歧义
       （deepseek 的 system-prompt 包连 tool-order 都有专属测试工具）""")