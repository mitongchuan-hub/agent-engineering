#!/usr/bin/env python3
"""
c01_bash_tool.py - codex_learn 第 1 步：Bash 即工具

codex 的哲学："Bash is all you need"——给模型一个 shell 执行能力，
它就能完成绝大多数任务（读文件、跑测试、git 操作、安装依赖…）。
codex 原版对应：tools/handlers/unified_exec（统一执行工具）。

这一章重建最小版本：execute_bash 工具 + 危险命令侦查。

核心设计（面试点）：
    1. 工具=执行器：subprocess 执行命令，返回 stdout/stderr/exit_code
    2. 看得见的结果：把输出原样回填给模型，模型基于真实输出继续推理
    3. 危险预检：执行前先做黑名单扫描（生产中还有沙箱/审批，见 c03/c04）

Usage:
    python c01_bash_tool/code.py        # 演示（无需 Key）
"""

import subprocess
import time
import json

# 危险命令黑名单（前缀匹配，生产还要叠加 沙箱+审批 两重保险）
DANGEROUS = ["rm -rf /", "mkfs", "dd if=", "shutdown", ":(){ :|:& };:", "curl | sh"]


class BashTool:
    """最小版统一执行工具。"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def execute(self, command: str) -> dict:
        """执行命令，返回结构化结果。"""
        # ① 危险预检：拦在黑名单前
        for bad in DANGEROUS:
            if command.strip().startswith(bad):
                return {"status": "blocked", "reason": f"危险命令：{bad}",
                        "command": command}
        # ② 限时执行（生产还要沙箱隔离，见 c04）
        try:
            proc = subprocess.run(command, shell=True, capture_output=True,
                                  text=True, timeout=self.timeout)
            return {"status": "ok", "exit_code": proc.returncode,
                    "stdout": proc.stdout[:500], "stderr": proc.stderr[:300]}
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": f"超过 {self.timeout}s"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class DemoLLM:
    """脚本模型：依次请求跑 python 算数 -> 列目录 -> 最终回答。"""

    PLAN = [
        {"id": "t1", "cmd": "python -c \"import math; print(math.sqrt(144))\""},
        {"id": "t2", "cmd": "echo hello && ls"},
    ]

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None):
        i = self.calls
        self.calls += 1
        if i < len(self.PLAN):
            c = self.PLAN[i]
            # 用 json.dumps 生成参数（千万别手拼 JSON —— 引号转义必踩坑，也别用 eval）
            args = json.dumps({"command": c["cmd"]})
            return {"role": "assistant", "content": None,
                    "tool_calls": [{"id": c["id"], "type": "function",
                                    "function": {"name": "execute_bash",
                                                 "arguments": args}}]}
        return {"role": "assistant", "content": "算完了，目录也看好了。", "tool_calls": None}


def run_agent(bash: BashTool, llm) -> str:
    """最小 Agent 循环（对应 learn-mini-agent s01，工具换成 Bash）。"""
    messages = [{"role": "user", "content": "帮我算 sqrt(144) 并看看目录里有什么"}]
    for step in range(1, 6):
        resp = llm.chat(messages)
        messages.append(resp)
        calls = resp.get("tool_calls") or []
        if not calls:
            return resp.get("content") or "(完成)"
        for tc in calls:
            cmd = json.loads(tc["function"]["arguments"])["command"]
            print(f"[agent] step {step}: bash \"{cmd}\"")
            t0 = time.time()
            result = bash.execute(cmd)
            print(f"[agent] step {step}: {result.get('status')} "
                  f"({time.time()-t0:.3f}s) -> {str(result)[:90]}")
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": str(result)})
    return "(达到上限)"


if __name__ == "__main__":
    print("演示：Bash 即工具（codex 哲学的最小版）\n")
    bash = BashTool()
    answer = run_agent(bash, DemoLLM())
    print(f"\n[agent] 最终回答：{answer}\n")

    print("危险预检演示：")
    for cmd in ["rm -rf / 重要目录", "echo 无害命令"]:
        r = bash.execute(cmd)
        print(f"  {cmd!r:20} -> {r.get('status')}: {r.get('reason') or r.get('stdout','')[:40]}")
    print("\n[结论] Bash 工具 = agent 的万能双手；危险预检是第一道闸（后面还有沙箱+审批）。")