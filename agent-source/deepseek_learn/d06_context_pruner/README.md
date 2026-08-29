# d06: 上下文裁剪 —— 先剪最划算的

> deepseek 源码对照：`packages/compaction/*`（compaction-tool-result-pruner 是亮点）
> 上一步：[d05 子 Agent](../d05_subagent/) ｜ 下一步：[d07 提示词组装](../d07_system_prompt/)

## 问题

上下文膨胀有三个来源：消息历史、**工具结果**、系统提示词。
codex c05 讲"历史压缩"（贵，要调 LLM）；本章讲更划算的做法——
**工具结果裁剪**：又长又重复的大 JSON/list 输出，只有骨架对后续有用。

## 方案：两级压缩，先便宜后贵

```
超预算？
  ① 裁剪工具结果（pruner）—— 零 LLM 调用，立竿见影
  ② 压缩消息历史（compactor）—— 一次小模型调用，最后手段
  ③ 截断丢消息 —— 尽量避免
```

## 原理（读 code.py）

### ① 结构化裁剪

```python
def prune(self, tool_name, raw):
    shape = self._shape(raw)          # JSON 骨架摘要：{"tasks": list[20]}
    head, tail = raw[:150], raw[-100:]  # 保留头尾
    return head + "…[中间 N 字符已裁剪]…" + tail
```
工具结果的特征：**头部是结构（键名），尾部是结尾（完整性），中间全是重复**——
剪中间损失最小。

### ② 结构化摘要（shape）

```python
def _shape(self, raw):
    # {"tasks":[{...}...20个]} -> {"tasks": list[20]}
    # 模型只需知道"有个 20 项的列表"，需要细节时再请求完整数据
```

### ③ 管线顺序决定成本

```python
def pipeline(messages, budget):
    if 超限: prune(tool 结果)      # 零成本
    if 还超限: compact(历史)       # 一次 LLM 调用
```
**执行顺序就是成本顺序**——这是和"一刀切截断"的本质区别。

## 运行

```bash
python d06_context_pruner/code.py
# 动作：pruned:1（只裁剪了工具结果）｜ 691/900，一次 LLM 都没花
```

## 自测问答

**Q：为什么不一律压缩历史？**
A：贵且慢（每次多一次模型往返）。工具结果裁剪往往已解决 70% 的膨胀（大 JSON 压缩率 80%+），先做免费的再做收费的。

**Q：剪掉的中间部分模型需要怎么办？**
A：两个出口：① shape 摘要告诉模型"这有 20 项"，需要时模型显式调工具拿完整数据；② deepseek/codex 都有"工具结果落地文件 + 按需重读"模式。

**Q：裁剪影响评测吗？**
A：影响——这正是评测集（s06/learn-mini-agent）存在的意义之一：裁剪策略变更后回归跑一遍，确保关键结论不因裁剪丢失。

## 延伸

- codex_learn c05：同样的目标，codex 侧重"历史压缩+hooks"；deepseek 多一个"工具结果独立裁剪"——两家组合 = 完整答案
- learn-mini-agent s04：窗口截断是地基，这里的两级压缩是进阶