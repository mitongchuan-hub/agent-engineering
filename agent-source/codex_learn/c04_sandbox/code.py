#!/usr/bin/env python3
"""
c04_sandbox.py - codex_learn 第 4 步：沙箱

杀招：即使命令通过了预检和审批，它依然可能干坏事（提权、写奇怪文件、访问网络）。
codex 的真实做法：三层沙箱
    - linux-sandbox（bwrap 非特权容器）
    - windows-sandbox-rs（Windows 作业对象）
    - sandboxing.rs（平台无关策略层）
本步重建"通用沙箱模型"（平台无关的教学版）：
    ① 允许列表：只放行白名单命令族
    ② 超时：任何命令限时，超时强杀
    ③ 产出隔离：结果打包，不动宿主机
    ④ 降权与网络禁用（模拟）：标注可扩展点

核心收获（面试点）：沙箱不是"拦截所有坏东西"，而是"默认全禁 + 显式放行"。

Usage:
    python c04_sandbox/code.py
"""

import subprocess
import time
from typing import List


ALLOWED_COMMANDS: List[str] = [
    "echo", "cat", "python", "node", "ls", "dir", "find", "grep", "wc",
]

# 演示用的"沙箱内允许"资源（教学版用字典模拟文件系统）
SANDBOX_FS = {
    "/tmp/app.py": "print('hello from sandbox')",
    "/tmp/secret.txt": "TOP-SECRET 不应该被读到",
}


class Sandbox:
    """教学版沙箱：允许列表 + 超时 + 虚拟文件系统。"""

    def __init__(self, timeout: int = 3):
        self.timeout = timeout
        self.calls: List[str] = []

    def run(self, command: str) -> dict:
        self.calls.append(command)
        # ① 允许列表：命令族白名单（codex 真实版还有 bwrap 的 --ro-bind 之力）
        parts = command.split(None, 1)
        prog = parts[0] if parts else ""
        if prog not in ALLOWED_COMMANDS:
            return {"status": "blocked", "reason": f"程序 {prog!r} 不在沙箱允许列表", "command": command}
        # ② 模拟虚拟文件系统：cat 只能读沙箱内的"文件"
        if prog == "cat":
            path = parts[1].strip() if len(parts) > 1 else ""
            if path in SANDBOX_FS:
                return {"status": "ok", "stdout": SANDBOX_FS[path]}
            return {"status": "blocked", "reason": f"文件 {path!r} 不在沙箱内", "command": command}
        if prog in ("python", "node"):
            # ③ 超时硬杀
            try:
                proc = subprocess.run(command, shell=True, capture_output=True,
                                      text=True, timeout=self.timeout)
                return {"status": "ok", "exit_code": proc.returncode,
                        "stdout": proc.stdout[:200]}
            except subprocess.TimeoutExpired:
                return {"status": "timeout", "reason": f"{self.timeout}s 超时强杀"}
        # echo 等安全的直接用
        try:
            proc = subprocess.run(command, shell=True, capture_output=True,
                                  text=True, timeout=self.timeout)
            return {"status": "ok", "exit_code": proc.returncode, "stdout": proc.stdout[:200]}
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "reason": f"{self.timeout}s 超时强杀"}


if __name__ == "__main__":
    print("演示：沙箱 = 默认全禁 + 显式放行\n")
    sb = Sandbox(timeout=2)
    tests = [
        "echo hello",                       # 允许列表内 -> ok
        "cat /tmp/app.py",                  # 沙箱内文件 -> 读到
        "cat /etc/passwd",                  # 沙箱外文件 -> 拦
        "rm -rf /",                         # 程序不在允许列表 -> 拦
        "python -c \"import time; time.sleep(10)\"",  # 超时 -> 强杀
        "python -c \"print(6*7)\"",         # 允许 -> ok
    ]
    for t in tests:
        r = sb.run(t)
        mark = "✅" if r.get("status") == "ok" else "🚫"
        print(f"  {mark} {t[:44]:44} -> {r.get('status')}: {r.get('reason') or r.get('stdout','')[:30]}")

    print("""
[结论] 沙箱哲学：默认拒绝 + 显式放行。
       codex 生产版在此基础上再加：
       - bwrap/作业对象做系统级隔离（文件系统只读绑定、网络禁用）
       - 降权（非 root 用户运行）
       - 与审批流联动（approvals.rs 里的 SandboxPermissions）""")