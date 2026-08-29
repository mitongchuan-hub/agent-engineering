#!/usr/bin/env python3
"""
p07_session_jsonl.py - pi_learn 第 7 步：JSONL 会话（带 codec）

pi 的 harness/session/jsonl/ 不是一个"把_dict_存上去"的草稿：
它有 codec（编码器）概念 + 版本化，格式可演进。

本步重建带 codec 的会话存储：
    ① codec：消息 <-> JSON 行（含版本号 v1）
    ② 追加写 + 坏行跳过（对齐 codex c06，但多了版本控制）
    ③ 版本迁移：v1 读到 v2 老文件也能处理（未知字段保留）

面试点：持久化格式要能"演化"——会话可能在老版本 Agent 崩溃后
被新版本打开，codec 与向后兼容决定"能不能救回老会话"。

Usage:
    python p07_session_jsonl/code.py
"""

import json
from pathlib import Path

SESSION_VERSION = 2                       # 当前格式版本


# ---------------------------------------------------------------- Codec

class CodecV1:
    version = 1

    def encode(self, msg: dict) -> dict:
        return {"v": self.version, **msg}   # 基础版：直接包版本号

    def decode(self, row: dict) -> dict:
        out = {k: v for k, v in row.items() if k != "v"}
        out["source_version"] = row.get("v", 1)
        return out


class CodecV2(CodecV1):
    """v2：给 assistant 消息的 content 加一个字段（举例：来源标记），
    保留 v1 的字段以实现向后兼容（旧行照读）。"""

    version = 2

    def decode(self, row: dict) -> dict:
        msg = super().decode(row)
        if msg.get("role") == "assistant" and msg.get("content"):
            # 老消息没有 marker 字段 -> 补默认值（迁移逻辑）
            msg["marker"] = msg.get("marker", "legacy-from-" +
                                    str(msg.get("source_version", "?")))
        return msg


# ---------------------------------------------------------------- 存储

class JsonlSession:
    def __init__(self, path: str, codec):
        self.path = Path(path)
        self.codec = codec

    def append(self, msg: dict) -> None:
        encoded = self.codec.encode(msg)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(encoded, ensure_ascii=False) + "\n")

    def load(self) -> list:
        if not self.path.exists():
            return []
        out = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(self.codec.decode(json.loads(line)))
                except json.JSONDecodeError:
                    continue              # 坏行跳过（崩溃残留）
        return out


# ---------------------------------------------------------------- 演示

if __name__ == "__main__":
    p = Path(__file__).resolve().parent / "session-v1.jsonl"
    p.unlink(missing_ok=True)

    print("演示：带 codec 的 JSONL 会话（版本迁移 + 向后兼容）\n")

    # 场景 1：老版本（v1 codec）写文件
    s1 = JsonlSession(str(p), CodecV1())
    s1.append({"role": "user", "content": "实现登录"})
    s1.append({"role": "assistant", "content": "采用 JWT 方案"})
    print(f"[v1] 老版本写入了 {len(s1.load())} 条消息")

    # 场景 2：升级到 v2 codec，老的 v1 文件照读（迁移）
    s2 = JsonlSession(str(p), CodecV2())
    loaded = s2.load()
    print(f"[v2] 新版本读取：{len(loaded)} 条（含 v1 旧行）")
    for m in loaded:
        print(f"     [{m['role']}] {m['content'][:14]:16}  marker={m.get('marker')}")

    # 场景 3：用 v2 继续写，新旧混存
    s2.append({"role": "assistant", "content": "补充：刷新令牌 7 天", "marker": "v2"})
    again = s2.load()
    print(f"[mixed] 混合会话共 {len(again)} 条，最后一条 marker="
          f"{again[-1].get('marker')}")

    print("""
[结论] codec 的价值（比 codex c06 多的一层）：
       1. 版本号随文件写 => 任何时候知道"这条是什么协议写的"
       2. 向后兼容 => 旧会话被新版本打开：老行补默认值，新字段可选
       3. 坏行跳过 => 崩溃残留不拖垮整个会话
       生产序列化一般再叠一层：schema 迁移测试 + 校验和（防静默损坏）""")
    p.unlink(missing_ok=True)