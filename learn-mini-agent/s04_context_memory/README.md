# s04: Context Memory —— 预算 + 窗口截断

> **Harness 层**：上下文管理是 Agent "活得久"的关键。
> 前一步：[s03 LLM 客户端](../s03_llm_client/) ｜ 后一步：[s05 简历匹配应用](../s05_resume_matcher/)

## 问题

Agent 聊得越久，`messages` 越长。模型上下文窗口有限（如 128K token），
**塞不下 = 请求报错或被迫截断丢信息**。这就是"上下文无限膨胀"问题。

我们手写的框架第一版就是裸的 `messages.append`——简单但迟早爆。

## 解决方案

上下文管理三大解法（**自测标准答案**）：

| 方案 | 做法 | 代价 |
|---|---|---|
| ① 窗口截断（本章） | 超预算就丢最早的消息 | 简单，但丢信息 |
| ② 摘要压缩 | 旧对话压成一段 summary 塞进 system | 需要多一次 LLM 调用 |
| ③ 向量检索（RAG） | 只把相关片段塞回上下文 | 需要向量库 |

生产级 Agent 通常是 **1+2+3 组合**。本章实现①，且有一个关键细节：
**截断时绝不拆散"一次工具调用的问答对"**。

## 工作原理

### ① 回合（turn）切割：保住工具调用对的完整性

```python
def _turns(self):
    """assistant 消息 + 其后的 tool/user 消息，直到下一条 assistant = 一个回合"""
    turns, cur = [], []
    for m in self.messages:
        if m.get("role") == "assistant" and cur:
            turns.append(cur); cur = []
        cur.append(m)
    ...
```
为什么重要？消息流长这样：

```
user      : 帮我查天气
assistant : tool_calls: get_weather(北京)   ← 发起
tool      : 25°C 晴                        ← 结果（必须和上面成对）
assistant : 北京今天 25 度
```
如果窗口截断只按"数量"切，可能留下孤零零的 `tool` 消息——模型看到"无源消息"会困惑甚至出错。**按回合切 = 切在整块上。**

### ② 从尾部向前保留

```python
for turn in reversed(self._turns()):   # 最新（最相关）的回合优先保留
    cost = sum(_size(m) for m in turn)
    if used + cost > self.char_budget and kept:
        break
```

### ③ 可观测性

```python
stats() -> {"total_msgs": 12, "sent_msgs": 3, "used_chars": 306, ...}
```
生产环境的 Agent 一定把这个打日志/埋点——**上下文用量是成本与质量的雷达**。

## 运行

```bash
python s04_context_memory/code.py
# 演示：灌 12 条消息，预算 300 字符，最终只发送最新 3 条（且成对完整）
```

## 练习

1. 把预算调大/调小，观察 sent_msgs 变化
2. 实现②摘要压缩：把被丢弃的回合交给一个小模型总结塞进 system
3. （进阶）🔍 为什么中文 1 字符≈1 token 的估算不够准？生产用 tokenizer 精确计量

## 自测问答

**Q：Context 无限膨胀怎么解决？**
A：三件套：窗口截断（保留最近的完整回合）、摘要压缩（旧内容沉淀为 summary）、向量检索（按需取回相关片段）。生产组合使用，且全部要可观测。

**Q：为什么不能简单地"丢掉最早的 N 条"？**
A：会破坏工具调用问答对的完整性（assistant 发起 + tool 回填必须成对），还会丢 system 指令。所以按"回合"为粒度保留，system 永远不丢。

**Q：token 估算怎么做？**
A：演示用字符数近似；生产用 tokenizer 精确计数（各家 SDK 都有 count_tokens），并据此设预算百分比，留余量给新回复。

## 延伸阅读

- s09：上下文爆掉时的保护性兜底（迭代上限、结果截断）
- 参考实现：`openai/codex` 的 `compact.rs` + `compact_model_fallback.rs`（压缩失败还能换便宜模型重试——比本章更进一步）