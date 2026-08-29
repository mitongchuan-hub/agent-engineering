# p04: 失败进流 —— 错误是流里的一个事件

> pi 源码对照：`types.ts` StreamFn 契约（stopReason: "error" | "aborted"）
> 上一步：[p03 并行工具](../p03_parallel_tools/) ｜ 下一步：[p05 provider](../p05_provider_layer/)

## 问题

模型调用"流式中途断了"（网络/超时/用户 Ctrl+C），怎么办？
传统：`try/except` 抛异常，上层 catch——UI 看不到中途原因，逻辑分支复杂。
pi：**失败也是流的一部分**。

## 方案（StreamFn 契约原文精神）

```
模型每次调用 = 返回一个流（不是只返回最终文本）
  流里有：delta 增量 / error 事件 / aborted 事件
  流结束时给最终消息：stopReason = stop | error | aborted | max_tokens ...
契约：不得抛异常 —— 失败必须编码进流
```

## 原理（读 code.py）

```python
def stream_example(kind):
    yield StreamEvent("delta", "正在生成前")
    if kind == "error":                       # 网络挂了：不抛！
        yield StreamEvent("error", "connection reset by peer")
        yield AssistantMessage("", "error", "connection reset...")
    elif kind == "aborted":
        yield StreamEvent("aborted", "user cancelled")
        yield AssistantMessage("", "aborted", "user cancelled")

def consume(stream):                          # 上层只认 stopReason，不 try/except
    for evt in stream: ...
    return final  # 带 stop_reason
```

## 运行

```bash
python p04_failure_in_stream/code.py
# 正常完成 stopReason=stop       内容='答案是 42'
# 网络错误  stopReason=error     error='connection reset by peer'
# 用户中断  stopReason=aborted   error='user cancelled'
```

## 面试问答

**Q：失败进流 vs 抛异常，什么时候选哪个？**
A：模型调用是"长期运行、部分结果已流出"的操作——此时异常会丢掉已流出部分；流式事件保留过程。真正"程序错误"（配置错）仍可抛。pi 也是混用：契约只约束"流本身的中断"。

**Q：对上层的好处？**
A：UI 能增量渲染 + 显示错误原因；逻辑层只按 stopReason 分支（重试/尊重中断/报错）统一处理——比"catch 后摸黑"强得多。

## 延伸

- learn-mini-agent s09：我们的 try/except 兜底；这里升级为"流式事件化"——可以回 s09 做一次重构练习
- p05：流式是 provider 层的标准形态（stream 接口）