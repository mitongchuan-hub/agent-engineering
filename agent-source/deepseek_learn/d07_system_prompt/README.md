# d07: 系统提示词组装 —— 提示词也是工程

> deepseek 源码对照：`packages/core/system-prompt/`（index.ts + tool-order.spec.ts）
> 上一步：[d06 上下文裁剪](../d06_context_pruner/) ｜ 完（deepseek_learn 收官）

## 问题

新手把系统提示词写成 800 字静态字符串：改一句要提心吊胆，
加功能要整段重排，调试时不知道哪句在起作用。

## 方案：分节组装（Section-Based）

```
assembler.add(Section("identity", "你是资深 HR 招聘顾问", order=10))
assembler.add(Section("rules",    "禁止编造分数",       order=20))
assembler.add(Section("memory",   "候选人是张三…",      order=25))
assembler.add(Section("legacy",   "旧功能描述", enabled=False))   # 可禁用
assembler.assemble(task)
```

## 原理（读 code.py）

### ① Section = 名字 + 内容 + 启用 + 顺序

```python
class Section:
    def __init__(self, name, content, enabled=True, order=100):
```
四个字段对应四个工程诉求：**可定位**（名字）、**可替换**（内容）、
**可启停**（enabled，A/B 测试直接关一节）、**可排序**（order）。

### ② 组装 = 排序 + 过滤 + 拼接

```python
ordered = sorted(s for s in self.sections if s.enabled, key=order)
body = "\n\n".join(s.render() for s in ordered)
```

### ③ tool-order：工具排序策略

```python
def tool_order_strategy(tools, important_first):
    return important + rest    # 重要工具前置
```
为什么有用？**首因效应**：模型在选择工具时倾向先看到的；
重要工具前置 = 减少空转 + 省 token（工具列表也占上下文）。

## 运行

```bash
python d07_system_prompt/code.py
# 组装结果：identity → rules → memory → tools_guide（legacy 被禁用不渲染）
# tool-order：compute_match/list_files 前置
```

## 自测问答

**Q：提示词为什么要"工程化"？**
A：静态长文的痛点：不可测试（哪句有效说不清）、不可组合（场景多时没法复用）、不可演进而焦虑（改一处影响全局）。分节后每节可单独评测（deepseek 的 system-prompt.spec / tool-order.spec 就是这么干的）。

**Q：记忆放哪一节？**
A：独立"memory 节"，靠近 rules 之后。好处：记忆更新只改一节（替换模板）；评测时可以 A/B（开/关记忆节看效果差异）。

**Q：工具排序怎么定？**
A：两步：① 按当前任务 scene 选出候选工具（不是全量）；② 高频/高价值工具前置。deepseek 把①做成动态渲染，②是 tool-order 策略。

## 收官

三家教学全部完成：**codex_learn（工程外壳）/ deepseek_learn（可插拔+契约）/ pi_learn（事件流+模型无关）**。
回总览 [agent-source/README.md](../README.md) 看三家对比与自测速查。