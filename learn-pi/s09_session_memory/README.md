# 第 09 章：Session 记忆与树形历史

## 本章问题

Agent 的内存不能只存在 Python 列表里。Pi 用 v3 JSONL 文件保存会话：第一行是 session header，后续每一行是一个带 `id`、`parentId` 的 entry。

```text
session header
  -> user A -> assistant A -> user B
                    \-> user C -> assistant C
```

当前 `leaf` 指向用户正在看的路径。切换分支只移动 leaf，不删除另一条路径。

## 源码调用链

```text
SessionManager.create/open()
  -> loadEntriesFromFile()
  -> _buildIndex()
  -> appendMessage()
     -> _appendEntry()
        -> parentId = leafId
        -> append JSONL line
  -> getBranch()/buildSessionContext()
```

Pi 的关键对象：

- `SessionHeader`：版本、Session id、cwd 和可选的父 Session。
- `SessionEntry`：所有历史节点的共同 `id`、`parentId`、timestamp。
- `leafId`：当前追加游标和活动分支终点。
- `buildSessionContext()`：沿 leaf 向根回溯，再将路径投影成模型上下文。
- `getTree()`：把平铺 entry 索引重建为树。

## 最小实现

本章的 `SessionManager` 支持：

```python
session = SessionManager.create("project", "session.jsonl")
root = session.append_message("user", "开始")
session.branch(root)
session.append_message("user", "另一条分支")
```

所有 append 都创建新 entry。`branch()` 只修改 leaf，`get_branch()` 从 leaf 沿 parent 链回到根，`build_context()` 只返回当前路径上的模型消息。

`custom` entry 可以保存扩展状态，但不自动进入模型上下文；这和后续 `custom_message` 的上下文可见性不同。

## JSONL 结构

```json
{"type":"session","version":3,"id":"...","cwd":"..."}
{"type":"message","id":"...","parentId":null,"timestamp":"...","message":{"role":"user","content":"..."}}
{"type":"message","id":"...","parentId":"...","timestamp":"...","message":{"role":"assistant","content":"..."}}
```

JSONL 的工程价值是追加写和局部恢复。示例加载时会跳过损坏行；生产 Pi 同样通过解析函数尽量恢复可读 entry。

## Branch 与 Fork

- **Branch**：同一个文件中移动 leaf，再从历史节点创建兄弟子树。
- **Fork**：创建新文件，复制原有 entry，header 使用新 Session id，并通过 `parentSession` 记录来源。

Branch 不复制消息，Fork 不共享后续追加。两者都不应该静默改写原历史。

## 动手运行

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s09_session_memory/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s09_session_memory.py
```

示例会创建内存 Session，先形成主路径，再从中间节点建立分支，最后打印活动上下文和整棵树。

## 关键测试

- header 和 parent chain 写入合法 JSONL。
- 重新打开文件可以恢复 leaf 和模型上下文。
- branch 不删除被放弃的历史。
- tree 能看到同一父节点下的两个子分支。
- fork 使用新 header，并保留 `parentSession`。
- 损坏行不会遮蔽其他有效 entry。
- custom entry 不进入上下文，branch summary 可以进入上下文。

## 与 Pi 的差异

| 本章实现 | Pi 生产实现 |
|---|---|
| entry id 使用短随机字符串 | Pi 使用随机短 id，并进行冲突检查 |
| append 立即写文件 | Pi 对首个 assistant 到达前有延迟 flush 逻辑 |
| message 内容使用简单字符串 | Pi 消息包含完整 LLM 内容、usage、时间戳和自定义类型 |
| build_context 只处理基础消息和 branch summary | Pi 还处理 compaction、model/thinking 变更及扩展消息 |
| fork 只提供核心复制路径 | Pi 还处理 labels、目标 cwd 和更多运行时状态 |

压缩 entry 和恢复策略在第 10 章实现；本章只固定记忆和树结构。

## 源码证据

上游仓库：`https://github.com/earendil-works/pi`  
固定提交：`9767ba275f3e9a5ee0f5c5342249b629ab1b2282`

- [`session-manager.ts`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/session-manager.ts)：Session header、entry 类型、追加、branch、tree 和 fork。
- [`session-manager.ts::buildSessionContext`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/session-manager.ts)：从当前 leaf 构建活动上下文。
- [`session-manager.ts::parseSessionEntries`](https://github.com/earendil-works/pi/blob/9767ba275f3e9a5ee0f5c5342249b629ab1b2282/packages/coding-agent/src/core/session-manager.ts)：JSONL 逐行解析和坏行跳过。

逐条定位见 [`UPSTREAM.md`](../UPSTREAM.md)。

## 下一章

第 10 章实现上下文压缩、重试和恢复，解释 compaction entry 如何改变模型可见路径而不破坏 Session 树。
