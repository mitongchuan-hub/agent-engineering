#!/usr/bin/env python3
"""
p06_branch_compaction.py - pi_learn 第 6 步：分支压缩

pi 的 harness/compaction/ 里有 branch-summarization。
"分支"指对话里出现的岔路：用户问 A，模型答 A；中途岔到 B 又回来——
分支内容不压掉，主线会被淹没。

本步重建：
    ① 把对话切成主线 + 分支（按"是否和被中断话题相关"判定，教学版用标记）
    ② 分支压成一条摘要（替换原文）
    ③ 主线按原样保留（重点信息不丢）

面试点：压缩不是"抹平一切"——要区分主线（保留原文）与分支（沉总结），
这是 branch-summarization 和"全局摘要"的关键差异。

Usage:
    python p06_branch_compaction/code.py
"""

# ---------------------------------------------------------------- 对话数据

CONVO = [
    {"role": "user",      "content": "实现用户登录"},
    {"role": "assistant", "content": "方案：JWT + 密码哈希"},
    {"role": "user",      "content": "（岔路）顺便看看怎么部署 Docker"},
    {"role": "assistant", "content": "Docker 用 docker compose + nginx 反代…"},
    {"role": "user",      "content": "（岔路）再查一下 JWT 过期时间配置"},
    {"role": "assistant", "content": "JWT 建议 24h，refresh token 7d…"},
    {"role": "user",      "content": "回到主任务：登录接口先做起来"},
    {"role": "assistant", "content": "好，按 JWT 方案写 /api/login…"},
]


# ---------------------------------------------------------------- 分支检测 + 压缩

def is_branch(msg: dict) -> bool:
    """教学版判定：内容带（岔路）标记，或含"回到主任务"= 主线恢复。"""
    c = msg.get("content", "")
    return "（岔路）" in c or "回到主任务" in c


def compress(conv: list) -> list:
    """把分支段落压成一条摘要，主线原文保留。"""
    out = []
    branch_buf = []
    for m in conv:
        c = m.get("content", "")
        if is_branch(m):
            branch_buf.append(c)                      # 进分支缓冲
            continue
        if branch_buf and "回到主任务" in c:          # 主线恢复了：沉总结分支
            out.append({"role": "user",
                        "content": "（分支摘要）" + "；".join(branch_buf)[:60] + "…"})
            branch_buf = []
        out.append(m)
    return out


if __name__ == "__main__":
    print("演示：分支压缩（主线保留 / 分支沉摘要）\n")
    print("压缩前：")
    for m in CONVO:
        print(f"    [{m['role']:9}] {m['content'][:30]}")

    print("\n压缩后：")
    for m in compress(CONVO):
        print(f"    [{m['role']:9}] {m['content'][:30]}")

    print("""
[结论] 分支压缩 vs 全局摘要：
       全局摘要：整段对话变一条 → 主线细节也丢了
       分支压缩：只沉"岔路"，主线原文保留 → 主任务不中断、细节不丢
       pi 的 branch-summarization 是"先识别再压缩"：
       压缩 < 识别（哪部分是主线）< 决策（沉哪条）——识别比压缩更难更有价值""")