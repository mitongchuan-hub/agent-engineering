# p06: 分支压缩 —— 沉岔路，保主线

> pi 源码对照：`harness/compaction/branch-summarization.ts`
> 上一步：[p05 provider](../p05_provider_layer/) ｜ 下一步：[p07 JSONL 会话](../p07_session_jsonl/)

## 问题

对话里常有"岔路"：用户问登录，中途岔去看 Docker、查 JWT 配置，再回主线。
全对话压缩 → 主线细节也丢；不压缩 → 分支淹没主线。

## 方案：先识别，再压缩

```
识别（哪个是主线 / 哪个是分支）
   └─ 分支：压成一条"分支摘要"
   └─ 主线：原文保留
   └─ 分支里的关键决策：可留作"决策记录"
```

## 原理（读 code.py）

```python
def is_branch(msg):        # 教学版用标记识别；生产版用话题聚类/相关性
    return "（岔路）" in c or "回到主任务" in c

def compress(conv):
    for m in conv:
        if is_branch(m): branch_buf.append(m)      # 进分支缓冲
        elif branch_buf and "回到主任务" in c:
            out.append({"role": "user",
                        "content": "（分支摘要）" + "；".join(branch_buf)[:60]})
            branch_buf = []
        out.append(m)                              # 主线原样
```

## 运行

```bash
python p06_branch_compaction/code.py
# 压缩前 8 条：主线(登录) + 分支(Docker/JWT) + 回到主线
# 压缩后：分支变 1 条摘要，主线两句保留
```

## 自测问答

**Q：分支 vs 全局压缩的本质区别？**
A：全局压缩"抹平一切"（主线细节也没了）；分支压缩"沉岔路、保主线"——主任务不中断的重要信息还在原文里。**识别比压缩更难**：识别错 = 把主线当分支沉了。

**Q：生产怎么识别分支？**
A：相关性打分（和新话题的相似度）、用户显式标记（"回到XX"）、窗口滑动检测话题漂移。pi 的 branch-summarization 是这套的思路浓缩。

## 延伸

- codex_learn c05 / deepseek_learn d06：另两家的压缩侧重"历史全文摘要"和"工具结果裁剪"——三家合起来 = 完整压缩矩阵（剪结果/沉分支/摘要历史）