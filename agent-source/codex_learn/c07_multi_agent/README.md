# c07: 多 Agent —— 分工、并行、转场

> codex 源码对照：`agent/control.rs`（33KB）、`agent/role.rs`、`agent/registry.rs`
> 上一步：[c06 会话持久化](../c06_session_persistence/) ｜ 下一步：deepseek_learn（团队协作更狠）

## 问题

单 Agent 的上下文里又装代码、又装历史、又装工具结果——全混在一起，
任务复杂时既乱又贵。**一个 Agent 干一行，一群 Agent 干一行**。

## 方案：主 Agent + 子 Agent

```
Manager（主 Agent，掌控全局）
  ├─ spawn ──▶ Planner    （独立上下文副本）
  ├─ spawn ──▶ Reviewer   （独立上下文副本，看 Planner 的产出）
  └─ 回收结果，统一决策
```

## 原理（读 code.py）

### ① 子 Agent = 独立上下文 + 独立能力

```python
class SubAgent:
    def __init__(self, name, system, skill): ...   # 独立的 system prompt + 技能

    def run(self, task):
        # 注意：它只看到自己的上下文，不知道主 agent 的其它对话
        return self.skill(task)
```
**上下文隔离**是子 Agent 的第一价值：互相不污染，各干各的。

### ② 转场控制（对应 codex control.rs）

```
spawn（派发任务）→ await（等结果）→ 决定（拿结果继续）→ 可能再 spawn
```

### ③ 角色 = 不同的 system + 不同的技能

```python
self.planner  = SubAgent("Planner",  "你负责拆解方案", self._plan_skill)
self.reviewer = SubAgent("Reviewer", "你负责挑毛病",   self._review_skill)
```
这里"角色"只是不同的函数+提示词；codex 的 `role.rs` 则把角色做成完整配置
（工具集、权限、模型都不同）。

## 运行

```bash
python c07_multi_agent/code.py
# [Manager] 同时派发 Planner 与 Reviewer...
# [Planner] 产出：方案：1)读取需求 2)设计接口...
# [Reviewer] 评审意见：缺少异常处理与回滚...
# [Manager] 最终决定：采纳方案并补充评审意见
```

## 面试问答

**Q：子 Agent 和主 Agent 共享上下文吗？**
A：不共享！这是重点。子 Agent 拿到的是一份"任务+相关材料"的副本，在独立上下文里干活，再把结果交回。这样主上下文不被中间过程污染，token 也更省。

**Q：什么时候该拆子 Agent？**
A：任务可并行（各自独立 → 并行省时）、任务需不同角色/模型（便宜干轻活、贵干重活）、任务太长（拆开压缩各自上下文）。

**Q：codex 的转场和 claude 的"剧本"区别？**
A：codex 转场是**代码控制**（control.rs 决定谁先谁后、何时回收）；claude 是**提示词剧本**（md 里写"先派 haiku 干 A 再派 sonnet 干 B"）。一个偏工程确定性，一个偏模型自主——各有适用场景。

## 延伸

- deepseek_learn d05：子 Agent 协议兼容层（subagent-claude-code / subagent-codex）
- claude-code 精读：里面 haiku/sonnet 成本分层的真实剧本