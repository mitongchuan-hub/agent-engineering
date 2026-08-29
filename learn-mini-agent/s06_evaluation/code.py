#!/usr/bin/env python3
"""
s06_evaluation.py - 评测集：用 Oracle 用例给 Agent 打分

Agent 上线后最常被问："你的 Agent 效果到底怎么样？"
没有度量就没有管理。本章给打分器做一套"回归评测"：

    评测集 = 一组 (输入, 期望输出) 的配对（Oracle 用例）
    评测指标：
      - 结论准确率   （verdict accuracy，分类任务核心指标）
      - 评分均误差   （score MAE，回归任务粒度指标）
    退出码：全部通过 -> 0（可挂 CI/流水线），存在失败 -> 1

这套思路一模一样可以迁移到 LLM 输出评测上：
人工标注 20 组"简历×JD"的期望结论，跑 Agent 对比相关度。

Usage:
    python s06_evaluation/code.py          # 跑评测，打印准确率与失败明细
    echo $LASTEXITCODE                     # 0 = 全部通过（可挂 CI）
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from s05_matcher.code import compute_match  # 复用上一步的打分器


# ---------------------------------------------------------------- ① Oracle 用例

CASES = [
    {  # 全命中：技能/年限/学历全达标
        "name": "case_backend_full", "note": "后端正岗全达标",
        "resume": "3 年经验，硕士，Java Spring Boot MySQL Redis Kafka Docker Kubernetes 分布式 高并发 微服务",
        "jd": "要求 3 年以上，本科及以上，Java Spring Boot MySQL Redis Kafka Docker Kubernetes 分布式 高并发 微服务",
        "verdict": "强烈推荐", "min": 95, "max": 100,
    },
    {  # AI 岗：技能 5/6，学历/年限达标，缺 Elasticsearch
        "name": "case_ai_missing_es", "note": "AI 岗技能缺口",
        "resume": "2 年经验，硕士，Python LLM RAG Agent LangChain",
        "jd": "要求 1 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch",
        "verdict": "强烈推荐", "min": 85, "max": 95,
    },
    {  # 学历不达标：本科 vs 硕士要求 -> 降档
        "name": "case_ai_low_edu", "note": "本科不满足硕士底线",
        "resume": "2 年经验，本科，Python LLM RAG Agent LangChain",
        "jd": "要求 1 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch",
        "verdict": "推荐", "min": 60, "max": 75,
    },
    {  # 应届生投 5 年经验岗：零技能重合
        "name": "case_junior_no_match", "note": "应届 vs 资深岗",
        "resume": "应届毕业生，本科，前端 HTML CSS JavaScript",
        "jd": "要求 5 年以上，本科及以上，Python Java 分布式 高并发",
        "verdict": "待定", "min": 0, "max": 40,
    },
    {  # 年限不足：技能/学历都行但 1 < 3 年
        "name": "case_years_fail", "note": "技能学历达标但年限不足",
        "resume": "1 年经验，硕士，Python RAG Agent",
        "jd": "要求 3 年以上，硕士及以上，Python RAG Agent",
        "verdict": "推荐", "min": 70, "max": 80,
    },
    {  # 转岗错配：5 年前端转 Java 后端，技能零重合（技能权重最高 -> 待定）
        "name": "case_frontend_mismatch", "note": "转岗零重合",
        "resume": "5 年经验，本科，前端 React Vue HTML",
        "jd": "要求 3 年以上，本科及以上，Java Spring MySQL 分布式 高并发",
        "verdict": "待定", "min": 45, "max": 55,
    },
]


# ---------------------------------------------------------------- ② 评测器

def run_eval(verbose: bool = True) -> tuple:
    """在全部用例上跑打分器并与 oracle 对比。返回 (是否全过, 准确率, 均误差)。"""
    passed, total, abs_errors = 0, 0, []
    for c in CASES:
        total += 1
        r = compute_match(c["resume"], c["jd"])
        ok_score = c["min"] <= r["overall_score"] <= c["max"]
        ok_verdict = c["verdict"] == r["verdict"]
        ok = ok_score and ok_verdict
        passed += ok
        if not ok_score:
            abs_errors.append(abs(r["overall_score"] - (c["min"] + c["max"]) / 2))
        if verbose:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {c['name']}: score={r['overall_score']} "
                  f"(期望 {c['min']}~{c['max']}), verdict={r['verdict']} "
                  f"(期望 {c['verdict']}), 缺口={', '.join(r['gap_skills'][:3]) or '无'}")
    accuracy = passed / total
    mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
    return passed == total, accuracy, mae


# ---------------------------------------------------------------- ③ 最小单测（内嵌）

class TestCore(unittest.TestCase):
    """两个最小单测：schema 生成 + 工具异常兜底。

    真实项目里这些放在 tests/（matcher-app 项目有 15 个）。"""

    def test_schema_generation(self):
        from s02_tool_registry.code import Tool
        def f(name: str, years: int, tags: list) -> str:
            """打分"""
            return name
        p = Tool(f).schema["parameters"]
        self.assertEqual(p["properties"]["years"]["type"], "integer")
        self.assertEqual(p["properties"]["tags"]["type"], "array")
        self.assertEqual(set(p["required"]), {"name", "years", "tags"})

    def test_tool_error_boundary(self):
        from s02_tool_registry.code import ToolRegistry
        r = ToolRegistry()
        @r.tool()
        def boom(x: int) -> int:
            raise ValueError("内部错误")
        out = r.call("boom", '{"x": 1}')
        self.assertIn("执行失败", out)  # 异常不能炸掉循环，要变成字符串回传


# ---------------------------------------------------------------- ④ 演示

if __name__ == "__main__":
    print(f"评测集：{len(CASES)} 个 Oracle 用例\n")
    ok, acc, mae = run_eval(verbose=True)
    print()
    print("========== 评测汇总 ==========")
    print(f"  结论准确率 : {acc:.0%} ({int(acc*len(CASES))}/{len(CASES)})")
    print(f"  评分均误差 : {mae:.2f} 分")
    print(f"  结果       : {'✅ 全部通过（exit=0，可挂 CI）' if ok else '❌ 存在失败（exit=1）'}")
    print()

    # 内嵌单测（最小形态，独立可跑）
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCore)
    print("[单测] 运行 TestCore...")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    ok = ok and result.wasSuccessful()

    sys.exit(0 if ok else 1)