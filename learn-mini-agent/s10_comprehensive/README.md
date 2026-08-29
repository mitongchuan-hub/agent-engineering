# s10: Comprehensive — 十步拼成一个完整应用

>[s09 健壮性](../s09_error_recovery/) ｜ **收官章**：learn-mini-agent 系列最后一步
> *"s01~s09 是零件，s10 是整机——点击运行，看看它能产出什么。"*

---

## 这一章是什么

前面每一步都是一个"零件"，本章把它们装配成 **一个完整应用**：

| 步骤 | 零件 | 在本章的用途 |
|---|---|---|
| s01 | Agent 循环 | 驱动整个流程 |
| s02 | ToolRegistry | 注册 4 个领域工具（一行装饰器一个） |
| s03 | ChatClient | （配 Key 时）真实模型接入 |
| s05 | compute_match | 核心打分器（规则层） |
| s07+s08 | MCP | 工具可外接（学过了，本章不绕弯） |
| s09 | 健壮性 | 异常兜底（学过了，随循环生效） |

拼起来完成真实数据流闭环：

```
list_files → read_text_file(输入×2) → match(×2) → write_file(报告) → 总结
```

---

## 两种运行方式

### ① 演示模式（无需 Key）——确定性管线

同一套工具、同一套顺序，脚本驱动，直接产出 `report.md`。
目的：**展示"完整流程长什么样"**，任何人可离线复现。

### ② 真实 LLM 模式（配 .env Key）——模型自主决策

把 4 个工具交给真实模型，它自己决定先调什么后调什么：

```
[agent] step 1: list_files
[agent] step 2: read_text_file ×3
[agent] step 3: compute_match ×2
[agent] step 4: write_file（2030 字符报告）→ 总结
```
模型还会遵守 s05 的铁律：分数一律来自规则工具的真实返回，不编造。
（仓库根 .env 配置后，这就是我们在"真实运行 Demo"里录下的行为。）

---

## 核心代码：工具注册只有 4 行

```python
@registry.tool(description="列出目录下的文件")
def list_files(directory: str): ...

@registry.tool(description="读取文本文件内容")
def read_text_file(path: str): ...

@registry.tool(description="规则打分器")
def match(resume_text: str, jd_text: str):
    return compute_match(resume_text, jd_text)      # 复用 s05

@registry.tool(description="写入文件（保存报告）")
def write_file(path: str, content: str): ...
```
这就是 s02 的成果兑现：**加一个工具 = 写一个函数 + 一行装饰器**。

---

## 代码走读（code.py）

- `build_registry()`：4 个领域工具（复用 s02 ToolRegistry + s05 compute_match）
- `run_pipeline()`：演示模式确定性管线（list→read→match×2→write→summary）
- `run_real()`：真实 LLM 驱动（ChatClient + registry.schemas()，模型自主决策）
- `data/`：resume.md + jd_ai.md + jd_backend.md（演示输入）
- `__main__`：有 Key → 真实模式；无 Key → 演示管线

调用链：`输入三份文本 → 4 工具装配 → 循环驱动 → report.md 落地`

---

## 试一下

```bash
# 演示模式（无需 Key）
python learn-mini-agent/s10_comprehensive/code.py
# [1] list_files → [2] read resume(359字符) → [3] match ai 93.0 / backend 100.0
# [4] write_file → 报告已保存 …/s10_comprehensive/report.md

# 真实 LLM 模式（仓库根 .env 配好 key 后）
python learn-mini-agent/s10_comprehensive/code.py
# ① 真实 LLM 模式 → 模型自主 4 轮决策 → 同样落地报告
```

---

## 练习

1. **加第 5 个工具**：`search_files(keyword, dir)`——练手"注册即生效"
2. **换模型跑**：.env 里换 DeepSeek/OpenAI，观察真实模式对话风格差异
3. **接 MCP 版**：把 match 换成 mcp_call_tool 外接（s07/s08 合体）
4. **加评测**：为 s10 写一条端到端冒烟（报告文件存在且含关键字段）——挂 CI
5. **白板复盘**：一张图画出 s01~s10 每个零件在最终应用里的位置

---

## 自测问答（整个系列的收尾）

**Q：这个 Agent 项目里，最难的是什么？**
A：把"模型的不确定性"和"工程的可控性"捏在一起——循环给骨架（s01），schema 给边界（s02），健壮性给兜底（s09），评测给信心（s06），MCP 给生态（s07/s08）。

**Q：如果生产化，还差什么？**
A：会话持久化与断点续跑（c06/p07）、审批流与沙箱（c03/c04）、多 Agent 分发（c07/d05）、流式 UI（p01）。这些就是 codex_learn / deepseek_learn / pi_learn / claude_learn 四个进阶教学库的内容。

**Q：为什么不直接用 LangGraph？**
A：先看懂了循环、状态、上下文这些本质，再用框架就是"使用已知之物"而不是"盲从"。这份仓库的进阶库覆盖了四家主流实现的机制重建——知其然也知其所以然。

---

## 下一步 · 四家进阶教学

- [codex_learn](../agent-source/codex_learn/README.md)：并行/审批/沙箱/压缩/持久化/多 Agent（c01~c07）
- [deepseek_learn](../agent-source/deepseek_learn/README.md)：状态机/插件钩子/Inbox/schema/子 Agent（d01~d07）
- [pi_learn](../agent-source/pi_learn/README.md)：事件流/steering/双轨并行/失败进流/provider（p01~p07）
- [claude_learn](../agent-source/claude_learn/README.md)：插件/白名单/剧本/钩子/命令/引擎（x01~x06）
- 总地图：[LEARNING_MAP](../LEARNING_MAP.md) ｜ 一键回归：[scripts/check_all.py](../scripts/check_all.py)