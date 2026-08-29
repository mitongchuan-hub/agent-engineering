# s01: Agent Loop —— 一个循环就够了

> **Harness 层**：循环是"模型与真实世界的第一个连接点"。
> 前一步：[总览](../README.md) ｜ 后一步：[s02 工具注册](../s02_tool_registry/)

## 问题

你提出一个问题给大模型：“帮我算一下 2+3”。模型能输出 `add(2, 3)` 这个调用意图，但**输出完就停了**——它不会自己去执行，也不会把结果拿回来继续推理。

你只能手动执行、把结果粘贴回对话框，它再输出下一条。**每多一次来回，你就多做一次“中间层”**。把这件事自动化，就是 Agent。

## 解决方案

一个 `while True` 循环：**模型要调工具就继续，不调就停**。整个过程只有两个信号：

| 信号 | 含义 | 循环动作 |
|------|------|---------|
| 响应里有 `tool_calls` | “我要用工具” | 执行 → 结果回填 → 继续 |
| 响应里没有 `tool_calls` | “我做完了” | 退出循环 |

```python
for step in range(1, max_iters + 1):
    resp = LLM(messages, tools)          # 1. 带工具定义问模型
    messages.append(resp)
    if not resp.tool_calls:              # 4. 模型说做完了
        return resp.content              #    -> 结束
    for tc in resp.tool_calls:           # 2. 模型要调工具
        result = call_tool(tc.name, tc.args)
        messages.append({"role": "tool", content: result})  # 3. 回填
```

## 工作原理（逐段读 code.py）

### ① 工具定义是“给模型看的说明书”

```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "add",
        "description": "两个整数相加",
        "parameters": {"type": "object", "properties": {...}, "required": [...]},
    },
}]
```
模型不执行代码，它只是“读说明书然后说出意图”。这个 JSON 就是 Function Calling 协议的载体。

### ② 工具执行是“给世界看的”

```python
def call_tool(name, arguments):
    args = json.loads(arguments)     # 模型给的工具参数是 JSON 字符串
    if name == "add":
        return str(add(args["a"], args["b"]))
```
模型 → 字符串参数 → 我们解析 → 真实执行 → 转成字符串回填。

### ③ 关键：消息是累积的

每轮我们都在 `messages` 上**追加**而不是替换：

```
user: 帮我算一下 2+3
assistant: tool_calls: add(2,3)
tool: 5
assistant: 答案是 5
```
模型靠完整的“因果链”才能理解上下文——这为 s04 的上下文管理埋下伏笔。

### ④ 安全上限

```python
max_iters = 20   # 防止模型陷入死循环烧钱
```
生产环境这是**标配**：Agent 循环没上限 = 无限烧 token。

## 运行

```bash
python s01_agent_loop/code.py
# 演示模式（无需 Key）：
#   [agent] 第 1 轮：调用工具 add({"a": 2, "b": 3})
#   [agent] 第 2 轮：无工具调用，循环结束

# 配 Key 走真实模型（任意 OpenAI 兼容服务）
LLM_API_KEY=sk-xxx python s01_agent_loop/code.py
```

## 练习

1. 给 FakeLLM 加一个“多轮工具调用”的脚本（第一轮 add、第二轮 multiply），观察 messages 如何累积
2. 把 `max_iters` 改小到 1，观察防御逻辑触发
3. 手写一个 `subtract` 工具并加入 TOOLS，看真实模型能不能用对

## 面试问答

**Q：Agent 和单纯 LLM 调用的区别？**
A：LLM 调用是"一次性问答"；Agent 是"循环"——模型可以请求执行工具、拿到结果继续推理，直到自己给出最终答案。区别的本质是**执行回路**。

**Q：tool_calls 是什么？**
A：模型响应里的结构化字段，声明"我想调用哪个函数、参数是什么"。需要遵循工具的 JSON Schema，参数以字符串形式给出，由宿主解析执行。

**Q：为什么工具结果要回填成 tool 消息？**
A：模型是"无状态的"，每一步决策只依赖 messages。不给它看工具结果，它就无法基于真实世界继续推理。

**Q：循环会不会死循环？**
A：会。所以要有 `max_iters` 上限和终止条件（无 tool_calls），生产环境还要加 token 预算和超时。s09 会展开讲健壮性。

## 延伸阅读

- s02：工具定义不再手写——函数签名自动生成 Schema
- s09：参数解析失败、工具抛异常时，怎么让 Agent 自愈
- 参考实现：`earendil-works/pi` 的 `packages/agent/src/agent-loop.ts`（同样的双层循环思路）