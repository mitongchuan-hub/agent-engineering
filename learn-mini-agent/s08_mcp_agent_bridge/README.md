# s08: Agent × MCP —— 工具变成可插拔服务

> **互操作层**：Agent 从"内置工具"进化到"外接生态"。
> 前一步：[s07 MCP Server](../s07_mcp_server/) ｜ 后一步：[s09 健壮性](../s09_error_recovery/)

## 问题

s07 我们写了个 MCP Server，但**谁来用它**？如果只有我们自己的机器连，
那和直接写个 Python 函数有什么区别？——还是没用上 MCP 的价值。

## 解决方案：桥接工具

在 Agent 的工具表里加一个"万能工具" `mcp_call_tool`：

```python
def mcp_call_tool(tool_name: str, arguments: dict = None) -> str:
    """通过 MCP 协议调用外部服务器上的工具"""
    with MCPClient(SERVER_CMD) as client:
        return client.request("tools/call", {"name": tool_name,
                                             "arguments": arguments})["content"][0]["text"]
```

对 Agent 来说，这只是一个普通工具；对世界来说，它打开了协议大门：

```
Agent(mcp_call_tool) ──▶ MCP Client ──stdio──▶ MCP Server（外部进程）
                                                    └─ compute_match / read_text_file / 任意
```

## 为什么这个设计好（面试三个点）

### ① 工具即插件

换工具 = 换一个 MCP Server 地址，Agent 代码**一行不改**。
试用新能力像插 U 盘，不用改循环、不用加 schema。

### ② 权限与故障隔离

外部工具跑在**独立子进程**。它崩了、卡了、甚至被恶意利用，
影响范围被限制在那个进程里——Agent 主循环毫发无损。

### ③ 生态互操作

Claude Code / Codex / 社区 1k+ 个 MCP Server 都是"即插即用"的能力池。
我们的 Agent 接入它们 = 免费获得整个生态。

## 参数兜底（为 s09 埋伏笔）

```python
if isinstance(arguments, str):
    arguments = json.loads(arguments)   # 模型把 JSON 对象序列化成字符串时兜底
```
这是开发中真实踩过的坑：模型调用工具时把 `arguments` 传成了 JSON **字符串**，
服务端 `**args` 直接炸。桥接层做一次类型归一，Agent 就稳了。s09 展开讲健壮性全家桶。

## 运行

```bash
python s08_mcp_agent_bridge/code.py
# [agent] 第 1 轮：mcp_call_tool(compute_match)
# [agent] 第 1 轮：MCP 返回 -> 总分 91.5
```

## 练习

1. 把 `SERVER_CMD` 指向 `s07_mcp_server/code.py` 的 `--serve`，然后加第二个工具
2. 故意让 Server 提前退出，观察 Agent 收到什么错误（错误是否被 Agent 消化）
3. （进阶）接入一个社区 MCP Server（如 GitHub MCP），让 Agent 调用外部服务

## 面试问答

**Q：Agent 需要把工具做进进程里吗？**
A：不一定。生产上两类混合：高频低延迟的（文件读写）内置；低频或有隔离需求的（外部 API、数据库、浏览器）走 MCP/插件进程。

**Q：MCP 调用比直接函数调用慢，值吗？**
A：值。多一次 IPC 换来了解耦、隔离、复用。而且 stdio 进程本地通信开销很小，毫秒级。

**Q：怎么让 Agent 自己发现有哪些 MCP 工具？**
A：tools/list 在启动时拉一次，把返回的 schema 合并进 Agent 的工具表；也可以在 prompt 里告知"还有哪些可用"。我们对齐了 function calling 的 schema 格式，可直接合并。

## 延伸阅读

- s09：参数兜底、错误自愈、迭代上限——让这套外接体系在生产里站得住
- 参考实现：resume-matcher 的 `app/mcp_tools.py`（含 `_coerce_args`，生产版）