#!/usr/bin/env python3
"""
p04_failure_in_stream.py - pi_learn 第 4 步：失败进流（StreamFn 契约）

pi 的 types.ts 里 StreamFn 契约（面试必背）：
    - Must NOT throw or return a rejected promise on failures
    - Failures must be encoded in the returned stream via protocol events
      and a final AssistantMessage with stopReason "error" or "aborted"

翻译成人话：**失败不是异常，是流里的一个事件**。

对比记忆点：
    传统做法（我们 s09）：try/except 抛 LLMError -> 上层 catch
    pi 的做法：每次模型调用返回一个流，流里最后一条消息 stopReason=error
       -> 上层按"流"统一处理，UI 能看到错误原因

本步重建：模拟一个会失败的流（网络错误 / 用户中断 / 超时），
验证"消费端不抛异常也能感知失败"。

Usage:
    python p04_failure_in_stream/code.py
"""

import time
from typing import Optional


# ---------------------------------------------------------------- 流类型

class StreamEvent:
    """流事件：delta（增量）/ error（错误）/ aborted（中断）/ end（正常结束）。"""

    def __init__(self, kind: str, payload: Optional[str] = None):
        self.kind = kind
        self.payload = payload or ""

    def __repr__(self):
        return f"<StreamEvent {self.kind}: {self.payload[:24]}>"


class AssistantMessage:
    """流的最终产物：content + stopReason（pi 协议的核心字段）。"""

    def __init__(self, content: str, stop_reason: str, error_message: str = ""):
        self.content = content
        self.stop_reason = stop_reason          # stop / error / aborted / max_tokens...
        self.error_message = error_message


# ---------------------------------------------------------------- 模型：三种失败形式的流

def stream_example(kind: str):
    """模拟开着流式响应时发生三种情况：正常 / 网络错误 / 用户中断。"""

    yield StreamEvent("delta", "正在生成前")
    if kind == "ok":
        yield StreamEvent("delta", "半句话")
        yield StreamEvent("end", "答案是 42")
        yield AssistantMessage("答案是 42", "stop")
    elif kind == "error":      # 调模型中途网络挂了：不抛异常，改为 error 事件
        yield StreamEvent("error", "connection reset by peer")
        yield AssistantMessage("", "error",
                               "connection reset by peer（网络错误发生在流中途）")
    elif kind == "aborted":    # 用户 Ctrl+C：同样编码进流
        yield StreamEvent("aborted", "user cancelled")
        yield AssistantMessage("", "aborted", "user cancelled")


# ---------------------------------------------------------------- 消费端（不抛异常）

def consume(stream) -> AssistantMessage:
    """上层按"流"统一消费：不 try/except，靠 stopReason 分支。"""
    for evt in stream:                       # 事件逐个到达（UI 可增量渲染）
        if isinstance(evt, AssistantMessage):  # 流结束：最终消息（要先判，它没有 kind）
            return evt
        if evt.kind == "delta":
            pass                             # 增量文本
        elif evt.kind == "end":
            pass                             # 正常结束前的最后增量
        elif evt.kind in ("error", "aborted"):
            print(f"     [flow] 收到失败事件：{evt}")
    return AssistantMessage("", "error", "流没给最终消息")


if __name__ == "__main__":
    print("演示：失败进流（三种流的 stopReason 统一处理）\n")
    for kind, label in [("ok", "正常完成"), ("error", "网络错误"), ("aborted", "用户中断")]:
        print(f"[{label}]")
        msg = consume(stream_example(kind))
        print(f"     stopReason={msg.stop_reason:<10} "
              f"content={msg.content!r} error={msg.error_message!r}\n")

    print("""
[结论] 失败的流式编码让上层无敌简单：
       1. UI：逐事件渲染增量；error 事件到了就显示错误（不用 catch）
       2. 逻辑：看 stopReason 分支（stop=完成 / error=重试 / aborted=尊重中断）
       3. 和 s09 的 try/except 互补：底层细节错误仍可抛，
          但"模型流本身的中断"统一走事件——这是 pi 比大多数框架先进的地方""")