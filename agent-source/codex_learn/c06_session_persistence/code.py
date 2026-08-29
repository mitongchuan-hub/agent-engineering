#!/usr/bin/env python3
"""
c06_session_persistence.py - codex_learn 第 6 步：会话持久化

Agent 跑一半断电了/超时了/重启了，凭什么恢复现场？
codex：rollout_reconstruction.rs（81KB 回放重建）+ thread-store。
pi：JSONL 会话文件（codec/repo/storage）。

本步重建教学版：把一整个对话（messages + 上下文统计）存成 JSONL，
重启后逐条回放恢复——模型接着上次的因果链继续干。

核心收获（面试点）：
    1. JSONL 追加写：每行一条消息，崩溃安全（不会整文件损坏）
    2. 回放即恢复：恢复 = 把存的每条消息原样读回 messages
    3. 断点续跑：恢复后 Agent 循环从最后一条继续

Usage:
    python c06_session_persistence/code.py
"""

import json
import os
from pathlib import Path
from typing import List


class SessionStore:
    """JSONL 会话存储：append + load。"""

    def __init__(self, path):
        self.path = Path(path)

    def append(self, msg: dict) -> None:
        """追加一条消息。每行独立 JSON —— 某条写坏不影响前面的。"""
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def load(self) -> List[dict]:
        """逐行回放：哪行坏了就跳过哪行（幂等恢复）。"""
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 跳过坏行（崩溃残留）
        return out

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


# ---------------------------------------------------------------- 演示

def simulate_turn(store: SessionStore, turn_id: int, content: str) -> None:
    """模拟 Agent 一轮：用户消息 + assistant 工具调用 + tool 回填，全部落盘。"""
    store.append({"role": "user", "content": content})
    store.append({"role": "assistant", "content": None,
                  "tool_calls": [{"id": f"t{turn_id}", "type": "function",
                                  "function": {"name": "read", "arguments": '{"path": "x.py"}'}}]})
    store.append({"role": "tool", "tool_call_id": f"t{turn_id}",
                  "content": f"文件内容第{turn_id}段"})


if __name__ == "__main__":
    sess = Path(__file__).resolve().parent / "session.jsonl"
    store = SessionStore(sess)
    store.clear()

    print("演示：JSONL 会话持久化与断点恢复\n")

    # —— 第 1 段会话：跑了 3 轮后"进程崩溃"——
    print("[第 1 次运行] 3 轮对话全部落盘")
    for i in range(1, 4):
        simulate_turn(store, i, f"问题{i}")

    # 模拟崩溃留下的坏行（演示容错）
    with sess.open("a", encoding="utf-8") as f:
        f.write("{破损的半个 JSON\n")

    # —— "重启"——
    print("[进程重启] 从 JSONL 回放恢复")
    msgs = store.load()
    print(f"[恢复] 读取 {len(msgs)} 条消息（坏行被跳过）")
    for m in msgs[:-3]:
        role = m["role"]
        brief = (m.get("content") or m.get("tool_call_id") or
                 m.get("tool_calls", [{}])[0].get("function", {}).get("name", ""))
        print(f"    [{role:9}] {brief[:40]}")

    # —— 继续干活 ——
    print("\n[恢复后继续] 追加第 4 轮，因果链连续")
    simulate_turn(store, 4, "问题4")
    msgs = store.load()
    print(f"[最终] 会话共 {len(msgs)} 条消息；最后 3 条：")
    for m in msgs[-3:]:
        print("   ", json.dumps(m, ensure_ascii=False)[:60])

    print(f"""
[结论] JSONL = 追加式、逐行独立、坏行可跳 → 天然崩溃安全。
       断点续跑 = load() 把消息原样放回 messages，循环从最后一条继续。
       codex 的 rollout_reconstruction 更进一步：不只存消息，还存"世界状态"
       与事件日志，可精确重建每一步。""")
    sess.unlink(missing_ok=True)  # 清理演示产物