# c03: 审批流 —— 危险操作谁说了算

> codex 源码对照：`tools/approvals.rs`（35KB）、`exec_policy.rs`
> 上一步：[c02 并行工具](../c02_parallel_tools/) ｜ 下一步：[c04 沙箱](../c04_sandbox/)

## 问题

黑名单永远漏：`rm -f ~/important` 不在 `rm -rf /` 黑名单里，但同样致命。
**静态规则防不住"看起来合理但后果严重"的操作。**需要一个"人/策略在决策环里"的机制。

## 方案：审批漏斗

```
命令 → 策略判定(auto/confirm/deny)
        ├─ deny    → 拦
        ├─ auto    → 放行（白名单）
        └─ confirm → ① 查缓存（同命令短时免审）
                     → ② 人工确认 / guardian AI 审查 / hook 自动决策
```

## 原理（读 code.py）

```python
class ApprovalPolicy:
    def judge(self, command):
        if startswith(黑名单):  return "deny"
        if startswith(白名单):  return "auto"
        return "confirm"          # 未知 = 保守确认
```
三层来源标注在审计日志：`policy`（策略）/ `cache`（缓存）/ `user`（人工）——
**每个决策都可追溯**。

### 一个细节：缓存审批（codex with_cached_approval）

```python
h = md5(cmd).hexdigest()[:8]
if h in cache and now < cache[h]:      # 5 秒内同一命令
    return True, "缓存免审", "cache"
```
为什么有价值？Agent 高频重复调用同一危险命令（如反复 `git push`）时，
每次都弹窗=体验灾难。短时缓存 = 安全与流畅的平衡点。

## 运行

```bash
python c03_approvals/code.py
# ✅ ls（白名单） ❌ rm -rf /（黑名单） ✅ git push（批准+缓存） ✅ git push（缓存免审）
```

## 面试问答

**Q：审批流和黑名单的区别？**
A：黑名单是"规则漏了 = 事故"；审批是"规则没覆盖的交给人在决策环里判"。codex 是 策略预判 + guardian AI 生成审查理由 + hooks 自定义决策 三层。

**Q：headless/CI 场景怎么办？**
A：hooks 可以配置成自动批准/拒绝（无交互）。codex 有 permission hooks，支持按命令前缀规则放行——CI 里全是白名单命令时零打断。

**Q：审批会拖慢 Agent 吗？**
A：会。所以白名单自动放行 + 短时缓存免审（with_cached_approval）两个机制把延迟压到最低；只有"真正危险的未知操作"才需要人。

## 延伸

- c04：审批通过后，命令还在沙箱里执行——两道独立防线
- 关联 learn-mini-agent s09：它讲异常自愈，这里讲"先别让它发生"