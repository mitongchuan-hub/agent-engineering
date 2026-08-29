# p07: JSONL 会话 —— 带 codec 的存档

> pi 源码对照：`harness/session/jsonl/`（codec.ts / repo.ts / storage.ts）
> 上一步：[p06 分支压缩](../p06_branch_compaction/) ｜ 完（pi_learn 收官）

## 问题

codex c06 教了 JSONL 存档；pi 多一层：**codec（编解码器）+ 版本控制**。
为什么需要？会话可能是在**老版本** Agent 崩溃后、被**新版本**打开的——
格式不兼容 = 老会话救不回来。

## 方案

```
存储 = JSONL（每行一条）+ Codec（版本化编解码）+ 迁移逻辑
   v1 写文件 ──▶ 升级 v2 后照读（未知字段保留、缺失字段补默认值）
   坏行跳过（崩溃残留不惜）
```

## 原理（读 code.py）

```python
class CodecV1:
    version = 1
    def encode(self, msg): return {"v": 1, **msg}
    def decode(self, row): ...          # 剥掉 v 字段

class CodecV2(CodecV1):
    version = 2
    def decode(self, row):
        msg = super().decode(row)
        # 迁移：老消息没有 marker 字段 → 补默认值
        msg["marker"] = msg.get("marker", f"legacy-from-{msg['source_version']}")
        return msg
```

## 运行

```bash
python p07_session_jsonl/code.py
# [v1] 老版本写入了 2 条消息
# [v2] 新版本读取：2 条（含 v1 旧行）→ marker 自动补为 legacy-from-1
# [mixed] v2 继续写，新旧混存正常
```

## 面试问答

**Q：JSONL 和 SQLite 怎么选？**
A：JSONL：零依赖、可读、追加写崩溃安全——适合本地会话。SQLite：查询/并发强——deepseek-harness 有 session-persistence-sqlite。按规模升级，接口保持异步友好。

**Q：codec 迁移什么时候触发？**
A：读行时按 `v` 字段分派 decoder；未来加字段只影响新行，老行走兼容分支。配一个"schema 迁移测试"（老样本必须能读）就是闭环了。

**Q：会话恢复后安全吗？**
A：恢复 = 信息恢复，不等于信任恢复。重启后危险操作重新审批（codex c03）——安全边界按会话重建。

## 收官

**三家教学全部完成。** 路线回顾：

| 学习库 | 主题 | 一句话精华 |
|---|---|---|
| [learn-mini-agent](../../learn-mini-agent/) | 手写框架 | 循环、schema、上下文、MCP、评测 |
| [codex_learn](../codex_learn/) | 工程外壳 | 并行、审批、沙箱、压缩、持久化、多 agent |
| [deepseek_learn](../deepseek_learn/) | 可插拔架构 | 状态机、插件钩子、Inbox、严格 schema、子 agent |
| [pi_learn](../pi_learn/) | 现代 Agent | 事件流、steering、双轨并行、失败进流、provider |

回总览 [agent-source/README.md](../README.md) 看对比表与面试速查。