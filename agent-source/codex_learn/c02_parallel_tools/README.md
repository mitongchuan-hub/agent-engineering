# c02: 工具并行执行 —— 两阶段 + 回填保序

> codex 源码对照：`tools/parallel.rs`｜ 同款实现：pi 的 `types.ts` ToolExecutionMode
> 上一步：[c01 Bash 工具](../c01_bash_tool/) ｜ 下一步：[c03 审批流](../c03_approvals/)

## 问题

模型一次请求 3 个工具调用（查北京天气、查 cpu、查杭州天气）。
串行执行要 2.2s；全部并发跑又怕乱序——**结果顺序必须跟模型的请求顺序一致**，
否则下一条推理读到错位的"天气=cpu 数据"。

## 方案：两阶段执行

```
阶段1 prepare（串行）：校验参数、准备环境   —— 便宜，出错早暴露
阶段2 execute（并发）：真正耗时操作         —— 线程池，互不阻塞
回填：结果按「发起顺序」排列，不按完成顺序  —— 因果不乱
```

## 原理（读 code.py）

```python
# prepare：串行校验
for c in calls:
    if name not in TOOL_TABLE: prepared.append(error)   # 早失败
    else: prepared.append(json.loads(arguments))

# execute：并发执行
with ThreadPoolExecutor(max_workers=4) as pool:
    futures[pool.submit(func, **args)] = index          # 每个工具一个线程
    for fut in as_completed(futures):                   # 谁先完谁先写
        results[futures[fut]] = ...                     # 按 index 对准

# 回填：按发起顺序！
return [results[i] for i in range(len(prepared))]
```

三个关键点：

1. **prepare 串行**：参数 404 在并发前就拦住，不浪费线程
2. **execute 并发**：`as_completed` 谁先完成谁落位，靠 index 对齐
3. **回填保序**：`results[i]` 按发起序输出 → 模型看到的因果链不乱

## 运行

```bash
python c02_parallel_tools/code.py
# 并行 0.81s vs 串行 2.20s（3 个慢调用）
# 输出顺序 = 请求顺序（北京 -> cpu -> 杭州），不是完成顺序
```

## 面试问答

**Q：并行执行工具，怎么保证消息顺序？**
A：结果容器按 index 对齐（`results[i]`），最后按发起序统一输出。执行完成的次序不影响回填次序——并发只影响速度，不影响因果。

**Q：为什么不全部并发？**
A：工具间可能有依赖（B 要用 A 的结果），且并发有资源上限（线程/连接/限流）。两阶段给"校验"留了串行口子，未来还能做依赖图（拓扑排序）。

**Q：线程隔离足够吗？**
A：线程内共享进程状态，发现问题成本高。codex 的并行工具实际走 IPC（exec-server）、进程级；这里用线程只为演示"并发+保序"的骨架。

## 延伸

- c03：并行来的危险命令，审批怎么接（审批在 prepare 后、execute 前）
- pi_learn p03：pi 的并行执行——还会发 `tool_execution_end` 事件（完成序）而消息按发起序，双轨制