# c05: 上下文压缩 —— 截断之上的进化

> codex 源码对照：`compact.rs`（30KB）、`compact_model_fallback.rs`
> 上一步：[c04 沙箱](../c04_sandbox/) ｜ 下一步：[c06 会话持久化](../c06_session_persistence/)

## 问题

learn-mini-agent s04 教了窗口截断：超预算就丢最早的。
但**丢的可能是关键信息**（用户早期给的约束、前几轮的工具结果）。
codex 的答案：不丢，**压缩**——把旧内容"提炼成摘要"再丢原文。

## 方案：带钩子的压缩生命周期

```
① 触发：token 预算超限
② PreCompactHook：压缩前干预（可自定义策略/拦下）
③ LLM 摘要：把旧消息压成 CompactionSummary（一条）
④ PostCompactHook：压缩后校验/记录
⑤ 兜底：主模型不可用 → 换便宜模型压缩（model fallback）
```

## 原理（读 code.py）

```python
old = messages[:-keep_latest]            # 旧消息 = 待压缩部分
latest = messages[-keep_latest:]         # 最新几条保留原文（语义最新鲜）
summary = summarizer.summarize(old)      # LLM 提炼（教学版用规则模拟）

ctx.messages = [{"role": "user", "content": f"（历史摘要）{summary} 继续任务"}] + latest
```

### 和 s04 截断的本质区别

| | 截断（s04） | 压缩（c05） |
|---|---|---|
| 旧消息去留 | 直接丢 | 提炼成摘要后再丢 |
| 信息密度 | 下降 | 语义保留（关键约束不丢） |
| 成本 | 零 | 一次小模型调用 |
| 兜底 | 无 | 压缩模型回退（fallback） |

### Hook 的价值（自测点）

```python
self.hook_log.append("[PreCompactHook] 触发压缩...")
self.hook_log.append("[PostCompactHook] 压缩完成：12 条 -> 1 条摘要")
```
压缩不再是一次"看不见的操作"，而是可观测、可拦截、可审计的生命周期——企业落地时必须这样。

## 运行

```bash
python c05_context_compaction/code.py
# 压缩前：20 条消息超预算 → 压缩后：5 条（1 摘要 + 4 最新）
# 持续对话超限 → 再次压缩（可循环）
```

## 自测问答

**Q：什么时候用截断、什么时候用压缩？**
A：压缩成本高（一次 LLM 调用），截断零成本。策略：大部分时间轻量截断 + 接近预算或关键轮次触发压缩；codex 还会在压缩前评估"压缩 vs 不压缩的收益"。

**Q：压缩会不会把关键信息压丢？**
A：会。所以：① 摘要模板强制保留"用户原始约束"；② 重要消息（如用户最后指令）永不压缩；③ PostCompactHook 可做质量校验（对比摘要 vs 原文的信息完整度）。

**Q：压缩谁来做？**
A：小/便宜模型（摘要任务不需要强大模型）。codex 的 compact_model_fallback：主模型不可用时自动换备用模型，保证流程不中断。

## 延伸

- c06：压缩解决"记不住"，持久化解决"重启后还在"
- deepseek_learn d06：它的 compaction 还有个工具——裁剪超长工具结果（context-pruner）