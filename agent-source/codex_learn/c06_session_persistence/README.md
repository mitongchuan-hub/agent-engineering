# c06: 会话持久化 —— 断电也能续上

> codex 源码对照：`rollout_reconstruction.rs`（81KB）、`thread-store/`
> pi 同款：`harness/session/jsonl/`（codec/repo/storage）
> 上一步：[c05 上下文压缩](../c05_context_compaction/) ｜ 下一步：[c07 多 Agent](../c07_multi_agent/)

## 问题

Agent 跑 1 小时，突然断电/超时/崩了。一切重来？
生产级 Agent 的答案：**会话是持久化的，恢复 = 回放**。

## 方案：JSONL 追加式存储 + 回放恢复

```
每轮对话 → append 一行 JSON（user / assistant / tool 消息）
恢复     → load() 逐行读回，坏行跳过
```

## 原理（读 code.py）

### 为什么用 JSONL 而不是一个 JSON 文件？

```python
def append(self, msg):
    with open(self.path, "a") as f:          # 追加模式：不重写整个文件
        f.write(json.dumps(msg) + "\n")      # 每行一条，互相独立

def load(self):
    for line in f:
        try: out.append(json.loads(line))
        except json.JSONDecodeError: continue   # 崩溃残留的坏行跳过
```

- **追加写**：写一半崩溃只坏最后一行，前面全好（JSON 整文件会全损）
- **逐行独立**：坏行可跳，其他消息照样恢复
- **幂等**：重复 load 不影响数据

### 恢复 = 把消息放回 messages

codex 的 rollout_reconstruction 更进一步：

| 维度 | 教学版 | codex 真实版 |
|---|---|---|
| 存什么 | messages（消息） | 消息 + 事件日志 + 世界状态 |
| 恢复精度 | 从最后一条继续 | 精确重演到任意 turn |
| 存储 | 本地文件 | thread-store + 云端 | 

## 运行

```bash
python c06_session_persistence/code.py
# 3 轮对话落盘 → "崩溃"（留一条坏行）→ 重启 load() 跳过坏行
# → 追加第 4 轮 → 因果链连续
```

## 自测问答

**Q：会话存什么粒度合适？**
A：至少存 messages（可回放续跑）；升级存事件日志（可回放 UI）；再升级存世界状态快照（可精确恢复工具/沙箱状态）。粒度越细成本越高，按需取舍。

**Q：并发写会话怎么办？**
A：单写者追加即可；多写者用锁或换 SQLite（deepseek-harness 有 session-persistence-sqlite）。

**Q：恢复后怎么保证安全？**
A：恢复会话 = 恢复信任级别。重要操作重新审批（c03）——"人能保证的是当前时刻，不是一小时前"。

## 延伸

- 关联 learn-mini-agent：s04 的 MessageBuffer + 本步 = 完整会话管理
- pi_learn p07：pi 的 JSONL 会话（含 codec 版本化，格式可演进）