# c04: 沙箱 —— Agent 的"无菌操作室"

> codex 源码对照：`core/src/sandboxing.rs`、`linux-sandbox/`、`windows-sandbox-rs/`
> 上一步：[c03 审批流](../c03_approvals/) ｜ 下一步：[c05 上下文压缩](../c05_context_compaction/)

## 问题

预检和审批挡得住"明着坏"，挡不住"偷着坏"：
命令没问题，但它可能读了你不想给它的文件、写坏了系统目录、偷偷发请求到外网。
**光靠检查命令文本=把门锁在门口，钥匙还在屋里。**

## 方案：沙箱 = 默认拒绝 + 显式放行

```
┌─────────────── Agent 进程 ───────────────┐
│ 你的代码                                 │
├─────────────── 沙箱边界 ─────────────────┤
│ 命令执行区：允许列表 / 虚拟文件系统 / 超时  │
└──────────────────────────────────────────┘
命令在"缩小版环境"里跑：能做的事被物理限制，而不是靠劝。
```

## 原理（读 code.py）

### 四道教学版限制

```python
# ① 程序白名单（codex 真实版用 bwrap 做系统级隔离）
if prog not in ALLOWED_COMMANDS:
    return {"status": "blocked", "reason": "程序不在沙箱允许列表"}

# ② 虚拟文件系统：cat 只能看到沙箱内的"文件"
if path not in SANDBOX_FS:
    return {"status": "blocked", "reason": "文件不在沙箱内"}   # cat /etc/passwd 被拦

# ③ 超时强杀：sleep(10) 的恶意命令 2 秒就没了
except subprocess.TimeoutExpired:
    return {"status": "timeout", "reason": "超时强杀"}

# ④ （可扩展）降权 / 禁网络 / 只读挂载 —— 见文末结论
```

### 教学版 vs codex 真实版

| 维度 | 教学版 | codex |
|---|---|---|
| 程序限制 | 白名单字符串 | bwrap 非特权容器 |
| 文件系统 | 虚拟字典 | 只读绑定 + 临时写层 |
| 网络 | 未实现 | 默认禁用、按权限开放 |
| 用户权限 | 未实现 | 降权运行 |

## 运行

```bash
python c04_sandbox/code.py
# ✅ echo hello      🚫 cat /etc/passwd（沙箱外）
# 🚫 rm -rf /（白名单外） ✅ python 算数
# 🚫 sleep(10)（超时强杀）
```

## 面试问答

**Q：沙箱和审批什么关系？**
A：两道独立防线。审批是"行为决策"（该不该做），沙箱是"能力限制"（做不出界）——即使审批漏了，沙箱也兜得住。

**Q：沙箱开销大吗？**
A：bwrap 等用户态沙箱开销很小（毫秒级启动）；容器/VM 级大。codex 在本地用 bwrap/作业对象，重活走远程执行，分级隔离。

**Q：Windows 怎么沙箱？**
A：codex 有 windows-sandbox-rs（作业对象 + ACL）。跨平台是 Agent 沙箱的工程难点，所以 codex 把平台差异封在独立 crate 里。

## 延伸

- c05：压缩——沙箱防"做坏事"，压缩防"记不住"
- pi_learn：pi 的沙箱走 exec 命令策略；deepseek_learn d06 有 sandbox 包（含 windows-acl）