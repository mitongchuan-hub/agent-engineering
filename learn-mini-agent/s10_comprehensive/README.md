# s10: Comprehensive —— 十步拼成一个完整应用

> **应用层**：最后一步，把一切串起来。
> 前一步：[s09 健壮性](../s09_error_recovery/)

## 这一章是什么

前面每一步都是一个"零件"：

| 步骤 | 零件 | 在本章的用途 |
|---|---|---|
| s01 | Agent 循环 | 驱动整个流程 |
| s02 | ToolRegistry | 注册 4 个领域工具 |
| s03 | ChatClient | （配 Key 时）真实模型接入 |
| s04 | MessageBuffer | （真实模式）上下文管理 |
| s05 | compute_match | 核心打分器 |
| s06 | 评测 | 打分器有据可依 |
| s07+s08 | MCP | 工具可外接 |
| s09 | 健壮性 | 异常兜底 |

拼起来 = **简历 × JD 匹配 Agent**，完成真实数据流闭环：

```
list_files → read_text_file(简历) → read_text_file(JD×2)
→ compute_match(×2) → write_file(报告) → 总结
```

## 两种运行方式

**① 演示模式（无需 Key）**：确定性管线，同一套工具同一套顺序，
直接产出 `report.md`——演示"Agent 干了什么"。

**② 真实模式（配 Key）**：真实 LLM 自主决策调哪些工具
（和完整项目 resume-matcher 行为一致）——演示"Agent 怎么决策"。

## 运行

```bash
python s10_comprehensive/code.py
# [1] list_files → [2] read resume → [3] match ×2 → [4] write_file
# 产出 s10_comprehensive/report.md

LLM_API_KEY=sk-xxx python s10_comprehensive/code.py   # 真实 LLM 模式
```

## 关键设计：工具注册只有 4 行

```python
@registry.tool(description="列出目录下的文件")
def list_files(directory: str): ...

@registry.tool(description="读取文本文件内容")
def read_text_file(path: str): ...

@registry.tool(description="简历×JD 匹配打分")
def match(resume_text: str, jd_text: str):
    return compute_match(resume_text, jd_text)   # 复 s05

@registry.tool(description="写入文件（保存报告）")
def write_file(path: str, content: str): ...
```
这就是 s02 的成果：**加一个工具 = 写一个函数 + 一行装饰器**。

## 自测问答（整个系列的收尾）

**Q：这个 Agent 项目里，最难的是什么？**
A：把"模型的不确定性"和"工程的可控性"捏在一起——循环给你骨架（s01），schema 给你边界（s02），健壮性给你兜底（s09），评测给你信心（s06），MCP 给你生态（s07/s08）。

**Q：如果生产化，还差什么？**
A：会话持久化与恢复（中间断点续跑）、token 预算计费、审批流（危险操作人工确认）、沙箱（代码执行隔离）、多 agent 分发、流式 UI（TUI/Web）。参考四巨头源码的对照表见 `agent-source/CODING_AGENTS_STRUCTURE.md`。

**Q：为什么不直接用 LangGraph？**
A：先看懂了循环、状态、上下文这些本质，再用框架就是"使用已知之物"而不是"盲从"。自测时先讲原理再讲框架取舍，是加分项。

## 延伸阅读

- 完整项目：`D:/work/xiangmu/resume-matcher/`（15 个单测 + 评测集 + MCP + .env 支持）
- 四大生产级源码结构对比：`D:/work/xiangmu/agent-source/CODING_AGENTS_STRUCTURE.md`
- 本项目学习路线：回到 [总览](../README.md)