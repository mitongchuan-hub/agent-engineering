# p03: 并行工具 —— 双轨制（事件按完成序 / 消息按发起序）

> pi 源码对照：`types.ts` ToolExecutionMode（sequential / parallel）
> 上一步：[p02 steering](../p02_steering/) ｜ 下一步：[p04 失败进流](../p04_failure_in_stream/)

## 问题

并行执行工具时，"谁先完成"（给 UI 看）和"按什么顺序回填"（给模型看）是两回事。
pi 的处理：**双轨分离**。

## 方案

```
execute 并发（线程池）
   ├─ 轨道1（事件）：tool_execution_end 按【完成顺序】发 —— 给 UI/进度
   └─ 轨道2（消息）：tool-result 按【发起顺序】落位 —— 给模型保因果
```

## 原理（读 code.py）

```python
# 轨道1：完成序（as_completed 到达即记录）
for fut in as_completed(futures):
    self.events.append({"name": ..., "finished_at": now})   # 谁先完谁先记

# 轨道2：发起序（按 index 组装）
return [json.dumps({"name": calls[i]["name"], ...}) for i in range(len(calls))]
```

运行输出让双轨肉眼可见：快的 `fetch_stats` 先出现在事件轨，
但消息轨的顺序永远是 天气→stats→搜索（发起序）。

## 运行

```bash
python p03_parallel_tools/code.py
# 轨道1｜事件流（完成序）：fetch_stats(发起位1) → search(2) → fetch_weather(0)
# 轨道2｜消息流（发起序）：msg@0 天气 / msg@1 stats / msg@2 search
```

## 自测问答

**Q：为什么事件按完成序、消息按发起序？**
A：观察者（UI/进度）看到"执行过程"，需要完成序；模型（消费者）看到的"逻辑结果"，必须是发起序（否则推理因果会错）。**观察轨和语义轨独立**——这是 pi/codex 双轨的共识。

**Q：并发安全怎么保证？**
A：写入用"按 index 的字典对齐"（results[idx]），最后一次性按序拼装——线程只写自己的槽位，无竞态。

## 延伸

- codex_learn c02：codex 的 parallel.rs 消息保序（单轨）；pi 多了事件轨
- p01：事件轨就是 p01 的事件流的一种事件