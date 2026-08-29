# x03: 多 Agent 剧本 —— 成本分层编排

> claude 源码对照：`plugins/code-review/commands/code-review.md`（真实多步剧本）
> 上一步：[x02 allowed-tools](../x02_allowed_tools/) ｜ 下一步：[x04 hooks](../x04_hooks/)

## 问题

一个命令的正文就是一份"剧本"：先派谁、并行几个、谁汇总。
claude 的真实剧本（code-review）长这样（前几步）：

```
1. Launch a haiku agent to check if the PR is reviewable.
2. Launch a haiku agent to list relevant CLAUDE.md files.
3. Launch a sonnet agent to view the PR and summarize changes.
4. Launch 4 agents in parallel to independently review the changes.
```

## 方案：成本分层 + 并行

| 模型 | 角色 | 成本 |
|---|---|---|
| haiku | 预检 / 摘要（轻活） | 便宜 |
| sonnet | 分析 / 评审（重活） | 贵 10× |

**便宜模型趟量大的活，贵模型只啃硬骨头。**

## 原理（读 code.py）

```python
def parse_playbook(text):
    # "Launch a <model> agent to <task>" → (model, task, 1)
    # "Launch N agents in parallel ..."  → (sonnet, task, N)
```
调度：并行行用线程并发执行；统计 token 与成本，和"全用贵模型"对比。

## 运行

```bash
python x03_playbook/code.py
# haiku ×1 预检 ... cost≈$0.030
# sonnet ×4 并发评审 ... cost≈$0.396
# 分层成本 vs 全贵成本 → 节省比例
```

## 自测问答

**Q：为什么贵模型不做预检？**
A：预检是"是否值得继续"的二值判断，haiku 足够且便宜 10 倍；大头的分析交给 sonnet。成本分层 = LLM 版"粗筛选细复审"。

**Q：并行评审的意义？**
A：4 个 agent 各自独立看同一 diff → 减少"单点盲区"，最后汇总 issues——并行还能把耗时压到近单次水平。对应 claude 的 confidence-based scoring。

**Q：和 codex c07 的转场控制区别？**
A：codex 用代码控制谁先谁后（control.rs）；claude 用**提示词剧本**声明（模型自主执行）。声明式更软、更省工程；代码式更确定、更好测试。

## 延伸

- x06：剧本放进引擎执行
- 对照 pi_learn p02（playbook 里还能加 steering/插话场景）