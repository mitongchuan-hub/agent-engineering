# s03: LLM Client —— 模型无关，协议统一

> **Harness 层**：模型接入层是所有 Agent 的公共地基。
> 前一步：[s02 工具注册](../s02_tool_registry/) ｜ 后一步：[s04 上下文管理](../s04_context_memory/)

## 问题

Agent 要干活必须接大模型。但你发现：
- OpenAI 有自己一套 SDK，DeepSeek 也有，智谱也有……
- 每家 base_url、鉴权、请求格式略有差异
- 今天用 GPT，明天想换 DeepSeek，业务代码改一片

**如果 Agent 代码里到处是厂商 SDK 调用，换模型就是一场灾难。**

## 解决方案

**协议统一 + 配置外置**。幸运的是：OpenAI 兼容协议已经成为事实标准
（DeepSeek/智谱/Moonshot/通义/千问 等全部兼容），所以只需要：

```python
class ChatClient:
    def __init__(self, base_url, api_key, model, ...):
        # 自动补 /v1（行业惯例：兼容端点都挂在 /v1 下）
        ...

    def chat(self, messages, tools=None) -> dict:
        # 所有厂商差异在这一行里被抹平
        ...
```

换模型 = 改 `.env` 里两个字符串，代码零改动。

## 工作原理

### ① 统一的入参/出参

```python
# 入参：消息 + 工具 schema
chat(messages, tools)
# 出参：标准 assistant 消息
{"role": "assistant",
 "content": "...",
 "tool_calls": [{"id", "function": {"name", "arguments"}}] | None}
```
这个返回值形状从 s01 起就是 Agent 循环唯一依赖的"世界接口"。

### ② 演示模式：假服务器验证真实协议

本章没有 Key 也能跑，靠的是一个**本地假 OpenAI 服务器**（`HTTPHandler` 实现 `/v1/chat/completions`）。
真实 `ChatClient` 发 HTTP 打它，能亲眼看到：

```
[协议观察] 发给服务器的请求体：
  model     : deepseek-chat
  messages  : [{"role": "user", "content": "计算 1+2"}]
  tools     : []
```
等配了 Key，把 transport 换成 openai SDK 分支即可——**协议透明可验证**。

### ③ 错误统一

```python
try:
    msg = client.chat.completions.create(**kwargs).choices[0].message
except Exception as e:
    raise LLMError(f"LLM 请求失败（{self.model}）: {e}")
```
上层只 catch `LLMError`，不用关心是哪家 500 了——为后续重试/降级铺路。

## 运行

```bash
python s03_llm_client/code.py                     # 演示：假服务器验证协议
LLM_API_KEY=sk-xxx python s03_llm_client/code.py  # 真实模型
```

## 练习

1. 把 `.env` 的 base_url 改成 `https://api.deepseek.com/v1` + model 改 `deepseek-chat`，跑到真模型
2. 给 ChatClient 加 `retry(times=3)`（µs 级退避）——生产必备
3. 加一个 `timeout` 参数并模拟慢响应，观察超时处理

## 面试问答

**Q：怎么做到模型无关？**
A：三层：① 协议层——OpenAI 兼容格式统一（stack 的请求/响应）；② 客户端层——ChatClient 封装 base_url/api_key/model；③ 配置层——.env 外置。业务代码只见 ChatClient。

**Q：为什么要自动补 `/v1`？**
A：OpenAI 兼容服务的公共端点约定在 `/v1` 下（如 `api.deepseek.com/v1`）。用户只给域名时补上，是"防御式编程"的典型例子。

**Q：LLM 调用失败的鲁棒性？**
A：错误统一为 LLMError → 上层可重试（指数退避）→ 可降级（切备用模型/备用厂商）→ 最终失败要保留上下文以便恢复。

## 延伸阅读

- s08：Agent 通过 MCP 调用外部工具——同样的"协议统一"思想，从 LLM 扩展到工具层
- 参考实现：`earendil-works/pi` 的 `packages/ai/`（40+ provider，是本章 ChatClient 的工业级放大版）