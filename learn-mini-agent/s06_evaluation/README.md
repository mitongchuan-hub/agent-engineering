# s06: Evaluation —— 用 Oracle 用例量化 Agent

> **质量层**：没有度量就没有改进。
> 前一步：[s05 简历匹配应用](../s05_matcher/) ｜ 后一步：[s07 MCP 协议](../s07_mcp_server/)

## 问题

自测官必问："**你的 Agent 效果怎么量化？**"
如果答"我试过几次，感觉还行"——直接暴露工程素养短板。

## 解决方案

**评测集（Evaluation Suite）**：一组 (输入, 期望输出) 的配对（Oracle 用例），
跑完自动算指标、给退出码。

```python
CASES = [
    {"name": "case_backend_full",
     "resume": "3 年经验，硕士，Java ...",
     "jd": "要求 3 年以上，本科及以上，Java ...",
     "verdict": "强烈推荐", "min": 95, "max": 100},   # 期望结论 + 评分区间
    ...
]
```

### 两个核心指标

| 指标 | 含义 | 类型 |
|---|---|---|
| 结论准确率（verdict accuracy） | 判定结论对不对 | 分类指标 |
| 评分均误差（score MAE） | 分数偏差多少 | 回归指标 |

### 退出码 = 可挂 CI

```
全部通过 -> exit 0（流水线放行）
有失败    -> exit 1（流水线拦截）
```

## 一个真实发生的"评测立功"故事（自测讲这个）

本项目开发时，s05 之前的手写框架里出现过这类 bug：

```python
# 单测用例：def f(name: str, years: int, tags: list) ...
# 期望 tags -> {type: "array"}
# 实际输出 -> {type: "string"}   ❌
```
原因是 `裸 list 类型（不带 List[str] 参数）的 get_origin 是 None`，
schema 生成器没识别成数组。**这类 bug 靠人肉 review 极难发现，
靠一条断言当场抓到。**这就是评测/单测存在的意义。

## 运行

```bash
python s06_evaluation/code.py
echo $LASTEXITCODE    # 0 = 全部通过（可挂 CI）
```

## 如何迁移到 LLM 评测（自测进阶）

打分器评测是二维的（输入→确定性输出）。LLM 输出是文本，评测升级为：

1. **人工标注**：20 组 简历×JD，标注期望结论（golden labels）
2. **对比相关度**：Agent 报告的结论 vs 标注，算准确率/Kappa
3. **可加自动化判官**：用强模型当裁判（LLM-as-a-judge），对比弱模型输出
4. **成本与质量双指标**：任务成功率之外，还要看 token 成本（s09 的上下文统计就是数据源）

## 自测问答

**Q：你怎么评测 Agent？**
A：三层：① 确定性组件（打分器/schema）用 Oracle 回归，量化到准确率；② 端到端用冒烟测试（完整链路不崩、产出报告）；③ LLM 文本输出用人工标注 + LLM-as-a-judge 对比。

**Q：评测挂了怎么办？**
A：先看失败用例归属哪一层（打分器 or 提示词 or 上下文）。规则层挂 = 逻辑 bug 或 oracle 过期；LLM 层挂 = 提示词/上下文问题，需人工复核。

**Q：Oracle 用例怎么维护？**
A：它是"需求说明书"的活体版本。加新能力 = 先写新 oracle 再改代码（测试驱动），防止回归。

## 延伸阅读

- 完整项目 matcher-app：15 个单测 + 6 个评测用例 + Mock 管线（CI 可全离线跑）
- 参考实现：`earendil-works/pi` 自带 `packages/evals/`——大厂也把评测当一等公民