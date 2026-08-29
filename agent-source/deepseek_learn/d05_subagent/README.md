# d05: 子 Agent —— 函数式调用的放大版

> deepseek 源码对照：`packages/subagent/`（11 个子包，114 文件，全仓最大组）
> 上一步：[d04 严格 schema](../d04_strict_schema/) ｜ 下一步：[d06 上下文裁剪](../d06_context_pruner/)

## 问题

任务太复杂时，一个 Agent 的上下文装不下（又骚又乱又贵）。
**拆！** 但拆得不好就是"伪多 agent"（共享状态互相污染）。

## 方案：契约化的子 Agent

```
Manager ──Task(标题/详情/载荷)──▶ SubAgent(独立上下文)
Manager ◀──Report(ok/摘要/数据)──  SubAgent
```

**子 agent = 一个"有参数的函数"**：Task in / Report out，中间全隔离。

## 原理（读 code.py）

### ① Driver 抽象（deepseek 最精巧的设计）

```python
class InProcessDriver:  # 进程内：直接调用，快，共享进程状态
class ForkDriver:       # fork 隔离：独立域，状态隔离（教学版用独立线程演示）
```
**运行*方式*是插件式的**：in-process（快）/ fork（稳）/ 远程（扩展）。
同一份子 agent 代码，换 driver 换隔离级别——工程上难得的两全。

### ② 深水区：协议兼容层

deepseek 的 subagent-claude-code / subagent-codex：
把 **Claude Code / codex 自己的子代理协议**翻译成 deepseek 的 Task/Report。
效果：别人家的 Agent 可以当我们的子 Agent，反之亦然——
**多 Agent 互操作做到协议层**，这是面试讲出来最惊人的点之一。

## 运行

```bash
python d05_subagent/code.py
# [Manager] 并行派发 ['analyzer', 'reviewer']
#   [analyzer] (in-process) 完成 ... 快
#   [reviewer] (fork) 完成 ...（独立域）
```

## 面试问答

**Q：什么时候用子 Agent？**
A：三条件任一：任务可并行（省时）、需要不同角色/模型（省钱省心智）、单上下文太长（省 token）。反之单 Agent 更简单可靠。

**Q：in-process 和 fork 怎么选？**
A：速度优先 in-process（共享内存零拷贝）；安全/隔离优先 fork 或远程（状态独立、崩溃隔离）。deepseek 两个都提供是为不同 stage：写信步（prototype）用 in-process，受信边界用 fork。

**Q：子 Agent 怎么"汇报"？**
A：Report 契约（ok/summary/data）。主 Agent 拿多个 Report 汇总决策；不等中间过程（上下文隔离的必然结果）。

## 延伸

- codex_learn c07：codex 的多 agent 侧重"转场控制"（control.rs），deepseek 侧重"协议与隔离"——合起来讲最完整
- pi_learn：pi 的 subagent 是 harness 里的内部能力，deepseek 把它做成开放协议