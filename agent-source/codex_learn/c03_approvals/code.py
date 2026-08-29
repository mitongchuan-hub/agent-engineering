#!/usr/bin/env python3
"""
c03_approvals.py - codex_learn 第 3 步：审批流

codex 里最值得学的工程外壳：危险操作不是"能不能做"，而是"谁说了算"。
对应源码：tools/approvals.rs（授权策略 + 路由 reviewer）。

三条审核通道（codex 真实做法，我们重建简化版）：
    ① exec_policy    命令匹配策略（白名单/黑名单/需要确认）
    ② guardian       AI 审查路由（给用户生成批准理由参考）
    ③ permission hooks 用户自定义钩子（CI 无头场景自动放行/拦截）
另外 codex 有 with_cached_approval：同类操作短时间免审（流畅度）

本步重建：策略判定 -> 审批漏斗 -> 缓存免审。

Usage:
    python c03_approvals/code.py
"""

import hashlib
import time


# ---------------------------------------------------------------- 策略层

class ApprovalPolicy:
    """命令三类判定：auto（放行） / confirm（需要确认） / deny（拒绝）。"""

    # 白名单前缀：绝对安全，直接放行
    AUTO_PREFIXES = ["ls", "pwd", "echo", "cat", "git status", "python -c", "grep"]
    # 需要确认：读改但可能有副作用
    CONFIRM_MARKERS = ["git push", "pip install", "npm install", "docker", "kill"]
    # 黑名单：一律拒绝（三板斧之外再加）
    DENY_MARKERS = ["rm -rf /", "mkfs", "dd if=", "sudo shutdown"]

    def judge(self, command: str) -> str:
        """返回 auto / confirm / deny + 原因。"""
        cmd = command.strip()
        if any(cmd.startswith(d) for d in self.DENY_MARKERS):
            return "deny"
        if any(cmd.startswith(a) for a in self.AUTO_PREFIXES):
            return "auto"
        if any(m in cmd for m in self.CONFIRM_MARKERS):
            return "confirm"
        return "confirm"  # 未知的保守起见都要确认


# ---------------------------------------------------------------- 审批漏斗

class ApprovalFlow:
    """审批漏斗：deny 直接拦 -> confirm 走人工/配置 -> 通过后进缓存。"""

    def __init__(self, policy: ApprovalPolicy, auto_approve: bool = False,
                 cache_ttl: float = 5.0):
        self.policy = policy
        self.auto_approve = auto_approve   # 模拟"用户总是同意"（headless 模式）
        self.cache_ttl = cache_ttl
        self._cache: dict = {}             # command-hash -> 过期时间
        self.decisions: list = []          # 审计日志

    def should_run(self, command: str) -> tuple:
        """返回 (允许?, 原因, 来源)。"""
        c = command.strip()
        verdict = self.policy.judge(c)

        if verdict == "deny":
            self.decisions.append(("deny", c, "policy"))
            return False, "策略拒绝", "policy"

        if verdict == "auto":
            return True, "白名单放行", "policy"

        # confirm：先查缓存（免审）
        h = hashlib.md5(c.encode()).hexdigest()[:8]
        if h in self._cache and time.time() < self._cache[h]:
            return True, "缓存免审", "cache"

        # 走"用户确认"（生产里是终端交互 / guardian 审查 / hooks）
        if self.auto_approve:
            self._cache[h] = time.time() + self.cache_ttl
            self.decisions.append(("approve", c, "user"))
            return True, "用户已批准（并写入缓存）", "user"
        self.decisions.append(("reject", c, "user"))
        return False, "用户拒绝", "user"


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    print("演示：审批漏斗（策略 -> 人工确认 -> 缓存免审）\n")
    flow = ApprovalFlow(ApprovalPolicy(), auto_approve=True)  # 模拟用户同意
    cmds = [
        "ls -la",                    # 白名单放行
        "rm -rf / 重要目录",          # 黑名单拒绝
        "git push origin main",      # 首次 confirm -> 批准+写缓存
        "git push origin main",      # 同一命令 -> 缓存免审
        "pip install numpy",         # 需要确认
        "docker rm -f container",    # 需要确认
    ]
    for c in cmds:
        ok, reason, src = flow.should_run(c)
        print(f"  {'✅' if ok else '❌'} {c:28} <- {reason}（{src}）")

    print("\n[审计日志]")
    for v, c, src in flow.decisions[-6:]:
        print(f"  {v:8} {c[:40]}")
    print("\n[结论] 三层防线：策略判断成本最低；人工确认最可靠；缓存平衡流畅度。")
    print("       codex 还叠加 guardian AI 审查（生成理由）与 hooks（CI 无头模式）。")