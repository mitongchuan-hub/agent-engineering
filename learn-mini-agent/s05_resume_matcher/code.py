#!/usr/bin/env python3
"""
s05_resume_matcher.py - 规则工具 + LLM 推理的混合应用

把前面 4 步拼成一个真实应用：简历 × 岗位 JD 匹配。

    设计思想（面试亮点）：
    「能把计算确定下来的，交给规则工具；需要推理的，交给 LLM。」

    - 技能重合度、年限、学历——这些都是"可计算的"，用规则（compute_match）
      → 可审计、可复现、零成本
    - 写报告、给建议、讲故事——这是"需要推理的"，交给 LLM
    → 混合架构 = 生产级 Agent 的标准做法

本文件演示"规则打分器"这一半（无需 Key 即可看完整结果）；
LLM 那一半在 s10 综合版里演示完整闭环。

Usage:
    python s05_resume_matcher/code.py
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List


# ---------------------------------------------------------------- ① 规则打分器

# 技能词表（教学演示用；生产用向量语义匹配更准）
SKILLS = [
    "python", "java", "c++", "c#", "go", "golang", "rust", "sql", "mysql", "redis",
    "postgresql", "mongodb", "elasticsearch", "kafka", "rabbitmq", "docker",
    "kubernetes", "k8s", "aws", "aliyun", "linux", "git", "ci/cd", "jenkins",
    "flink", "spark", "hadoop", "hive", "pytorch", "tensorflow", "llm", "rag",
    "agent", "langchain", "langgraph", "fastapi", "flask", "django", "spring",
    "springboot", "react", "vue", "html", "css", "javascript", "typescript",
    "node.js", "nginx", "微服务", "分布式", "高并发",
]

_EDU_LEVEL = {"博士": 5, "硕士": 4, "本科": 3, "大专": 2, "高中": 1}


def _extract_skills(text: str) -> set:
    low = text.lower()
    return {s for s in SKILLS if s in low}


def _extract_years(text: str) -> List[int]:
    return [int(x) for x in re.findall(r"(\d+)\s*年", text)]


def _edu_level(text: str) -> int:
    return max((_EDU_LEVEL[k] for k in _EDU_LEVEL if k in text), default=0)


def compute_match(resume_text: str, jd_text: str) -> dict:
    """★确定性打分器：同一输入永远同一输出（可测试、可审计）。"""
    resume_skills, jd_skills = _extract_skills(resume_text), _extract_skills(jd_text)
    matched = resume_skills & jd_skills
    skill_coverage = round(len(matched) / len(jd_skills), 2) if jd_skills else 1.0
    gaps = sorted(jd_skills - resume_skills)

    resume_years = max(_extract_years(resume_text)) if _extract_years(resume_text) else 0
    jd_min_years = min(_extract_years(jd_text)) if _extract_years(jd_text) else 0
    years_ok = resume_years >= jd_min_years

    resume_edu, jd_min_edu = _edu_level(resume_text), _edu_level(jd_text) or 3
    edu_ok = resume_edu >= jd_min_edu

    # 权重：技能 50 / 年限 25 / 学历 25（可调）
    overall = round(skill_coverage * 50 + (100 if years_ok else 0) * 0.25
                    + (100 if edu_ok else 0) * 0.25, 1)
    return {
        "jd_skills": sorted(jd_skills), "matched_skills": sorted(matched),
        "skill_coverage": skill_coverage, "gap_skills": gaps,
        "resume_years": resume_years, "jd_min_years": jd_min_years, "years_ok": years_ok,
        "edu_ok": edu_ok, "overall_score": overall,
        "verdict": "强烈推荐" if overall >= 80 else ("推荐" if overall >= 60 else "待定"),
    }


# ---------------------------------------------------------------- ② 演示数据

SAMPLE_RESUME = """# 张三 | 后端 / AI 应用开发工程师
学历：硕士
工作经历：3 年，星辰科技后端工程师
- Spring Boot + MySQL + Redis + Kafka，支撑日均 500 万请求
- 基于 LangChain + RAG 实现知识库问答系统，检索命中率提升 30%
- 使用 AutoGen 搭建多智能体客服助手
- Docker + Kubernetes + CI/CD
技能：Python、Java、FastAPI、Spring Boot、MySQL、Redis、Kafka、
      Docker、Kubernetes、Nginx、LLM、RAG、Agent、LangChain、LangGraph、
      Linux、Git、分布式、高并发、微服务
"""

JD_BACKEND = """# 后端开发工程师（Java）
经验：3 年以上 ｜ 学历：本科及以上
要求：Java、Spring Boot、MySQL、Redis、Kafka、Docker、Kubernetes，
     微服务架构、分布式、高并发
"""

JD_AI = """# AI 应用工程师（LLM Agent 方向）
经验：2 年以上 ｜ 学历：硕士及以上
要求：Python、LLM、RAG、Agent、LangGraph、LangChain、Elasticsearch
"""


# ---------------------------------------------------------------- ③ 演示

if __name__ == "__main__":
    print("演示：规则打分器（确定性、可审计）\n")
    results = {}
    for name, jd_text in [("backend_engineer", JD_BACKEND), ("ai_engineer", JD_AI)]:
        r = compute_match(SAMPLE_RESUME, jd_text)
        results[name] = r
        print(f"▶ {name}")
        print(f"  总分：{r['overall_score']} ｜ 结论：{r['verdict']}")
        print(f"  技能覆盖率：{r['skill_coverage']*100:.0f}% ｜ "
              f"匹配：{', '.join(r['matched_skills']) or '无'}")
        print(f"  缺口：{', '.join(r['gap_skills']) or '无'}")
        print(f"  年限：简历{r['resume_years']}年 vs 要求{r['jd_min_years']}年 "
              f"{'✅' if r['years_ok'] else '❌'} ｜ 学历 {'✅' if r['edu_ok'] else '❌'}")
        print()

    # 结论是真的可复现：同一输入 -> 同一输出（这是"规则"最大的价值）
    again = compute_match(SAMPLE_RESUME, JD_AI)
    print(f"[可复现性验证] 重复调用同一输入 -> 仍得 {again['overall_score']} 分 "
          f"（{'✅ 一致' if again == results['ai_engineer'] else '❌ 不一致'}）\n")

    print("说明：'写报告/给建议'这类需要推理的事交给 LLM 的完整闭环，"
          "见 s10_comprehensive。")
    sys.exit(0)