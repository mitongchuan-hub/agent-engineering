# s07: MCP Server —— 从零拆掉协议的黑盒

> **互操作层**：MCP 是 2025 年 Agent 生态的"USB-C 接口"。
> 前一步：[s06 评测集](../s06_evaluation/) ｜ 后一步：[s08 Agent × MCP](../s08_mcp_agent_bridge/)

## 问题

你的 Agent 内置了 `compute_match`、`read_text_file`……但别的 Agent（Claude Code / Codex / 同事的项目）
**用不了你的工具**。每个人都在重复造轮子。
而使用方最怕的是：每家工具协议都不一样，集成一次累死一次。

**需要一个统一接口，让"工具"和"Agent"解耦。**

## 解决方案：MCP

MCP（Model Context Protocol）由 Anthropic 提出，已经成为事实标准。
它的本质被大量教程包装得很吓人，其实只有两句话：

```
MCP = JSON-RPC 2.0（消息格式） + stdio（传输：每行一个 JSON）
```

本章用纯标准库实现了一遍：`MCPToolServer`（分发） + `MCPClient`（握手调用），没有官方 SDK。

## 工作原理

### ① 生命周期四步（自测手绘）

```python
# Client 侧（我们实现的 MCPClient）：
client.request("initialize", ...)               # ① 握手声明版本/能力
client.put_notification("notifications/initialized")  # ② 通知初始化完成
client.request("tools/list")                    # ③ 问"你有什么工具？"
client.request("tools/call", {"name": ..., "arguments": ...})  # ④ 调用
```
前两步是"手拉手认识"，后两步才是干活。

### ② 协议错误 vs 业务错误（自测细节题）

```python
# 工具不存在 / 方法不存在   -> JSON-RPC error 字段（协议层问题）
return self._err(rid, -32601, f"未知方法: {method}")

# 工具执行失败（参数不全等） -> result.isError = true（业务层问题）
return self._ok(rid, {"content": [...], "isError": True})
```
区分这两层的意义：**协议层坏了要换客户端/修代码；业务层坏了只需改工具实现**，
调用方甚至不用变。演示里两条路径都打给你看了。

### ③ 工具返回统一包一层

```python
{"content": [{"type": "text", "text": "<JSON 字符串>"}], "isError": false}
```
MCP 规定所有工具返回都包成 `content` 数组——这样工具可以返回文本、图片、结构化数据，
而 Agent 只需要解析 `text`。

## 运行

```bash
python s07_mcp_server/code.py             # 演示：完整生命周期 + 错误分层
python s07_mcp_server/code.py --serve     # 常驻成 Server，供任意 MCP 客户端连接
```

## 练习

1. 给 MCP_TOOLS 加 `read_text_file`（文件读取），重新跑 tools/list
2. （进阶）把 transport 从 stdio 换成 HTTP/SSE——MCP 的传输层是可替换的
3. （进阶）查一下官方 SDK 的 `tools/call` 返回结构，对比本章实现差在哪

## 自测问答

**Q：MCP 和 Function Calling 什么关系？**
A：Function Calling 是"模型↔宿主"的协议（模型请求调函数）；MCP 是"宿主↔外部工具服务"的协议。它让工具在网络边界上被复用：一个 MCP Server 可以有任意客户端接入。两者是分层关系，不冲突。

**Q：MCP 的传输有哪几种？**
A：stdio（本地子进程，本章）、HTTP with SSE（远程）、Streamable HTTP。都跑 JSON-RPC。

**Q：为什么工具结果要 isError 字段而不是抛异常？**
A：业务失败（参数错、文件不存在）是"预期内的非预期"，客户端应该能拿到错误内容展示给 LLM 让它自愈；协议错误（未知方法）是"不该发生的"，走 JSON-RPC error。

## 延伸阅读

- s08：让我们的 Agent 当 MCP 客户端，动态外接外部服务器
- s09：arguments 参数类型兜底（模型把 JSON 对象传成字符串的真 bug）
- 参考实现：matcher-app 的 `mini_agent/mcp.py`（本协议的完整版，封装更好）