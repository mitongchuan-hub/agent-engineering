# s09: Error Recovery —— 摔不坏的 Agent

> **健壮性层**：真实世界的 Agent 必须把失败当数据流。
> 前一步：[s08 Agent × MCP](../s08_mcp_agent_bridge/) ｜ 后一步：[s10 综合成品](../s10_comprehensive/)

## 问题

教学环境里模型乖巧听话；真实生产里，模型什么都会干：
- 把 `arguments` 传成 JSON **字符串**而不是对象
- 参数类型传错、缺字段
- 请求一个不存在的工具
- 工具本身抛异常（除零、文件不存在、网络超时）
- 死循环式地反复调工具——烧你的钱

**Agent 的健壮性 = 把每一个失败都变成可处理的数据，而不是崩溃。**

## 四道防线（每个都是真实踩过的坑）

```
① 参数兜底   arguments 可能是字符串 → _coerce_args 统一转 dict
② 结果截断   超长工具输出截断 → 防撑爆上下文
③ 错误回传   工具异常变字符串回传 → 模型自愈重试
④ 迭代上限   max_iters 兜底 → 防死循环烧钱
```

### ① 参数兜底：一个真实 Bug

开发时某模型（gpt-5.5）调用 `mcp_call_tool` 时传入：
```json
{"tool_name": "compute_match", "arguments": "{\"path\":\"...\"}"}
```
内层 `arguments` 是**字符串**而非对象——服务端 `**args` 当场 TypeError。
桥接层加一行归一，Agent 稳了：

```python
def _coerce_args(arguments):
    if isinstance(arguments, str):
        return json.loads(arguments)      # "{\"a\":1}" -> {"a":1}
    return arguments or {}
```

### ③ 错误回传 = 自愈入口

```python
except TypeError as e:
    return f"工具调用参数错误：{e}。请参考工具 schema 修正参数后重试。"
except Exception as e:
    return f"工具执行失败：{type(e).__name__}: {e}"
```
关键是**不抛异常**。错误以字符串回到消息流 → 模型"看到"错误 → 修正 → 重试。
演示里模型算 10/0 报错后自己改 b=2 完成——这就是自愈。

### ④ 迭代上限

```python
for step in range(1, max_iters + 1):
    ...
return "(到达迭代上限，强制收尾——防线④生效)"
```
模型永远调工具时，这是最后一道闸。生产上还配合 token 预算与超时。

## 运行

```bash
python s09_error_recovery/code.py
# 场景A 参数兜底一次成功
# 场景B 除零报错 → 模型自愈
# 场景C 永远调工具 → 上限兜底
```

## 练习

1. 让 Executor 抛出网络超时错误，观察错误字符串怎么回传
2. 把 `MAX_TOOL_RESULT` 调成 10，看截断提示
3. （进阶）加"重试 3 次后放弃"策略：连续同类错误次数超过阈值就停

## 自测问答

**Q：工具调用失败，Agent 会崩吗？**
A：取决于设计。把异常吞进错误字符串回传 → 不崩，还给了模型自愈机会；直接抛 → 循环中断。生产做法是"回传 + 限定重试次数后放弃"。

**Q：怎么防死循环？**
A：四道闸：max_iters、token 预算、超时、以及"连续相同工具调用 N 次"检测。申请预算前想清楚每道闸的成本。

**Q：截断工具结果会不会丢信息？**
A：会，但可控。策略：默认截断 + 模型需要时显式请求完整内容（大文件分批读）；或者对结构化输出只保留关键字段。

## 延伸阅读

- s04：上下文预算——截断结果的"上一道闸"
- 参考实现：resume-matcher 完整版（异常三层兜底：桥接层→执行器→循环）