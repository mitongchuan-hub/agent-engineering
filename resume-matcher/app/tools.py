"""应用层工具：简历×JD 匹配 Agent 的「手」。

设计思想（面试亮点）：
    把**可以确定计算的**交给规则工具（技能重合、年限、学历都算得出来），
    把**需要推理的**交给 LLM（写报告、给建议、讲故事）。
    确定性工具的结果可审计、可复现——这就是"工具化 Agent"的核心工程价值。
"""
from __future__ import annotations

import json
import os
import re
from typing import List

# 通用技能词表（面试可以说：真实场景应从内部技能库/向量语义匹配，这里用词表做教学演示）
SKILLS = [
    "python", "java", "c++", "c#", "go", "golang", "rust", "sql", "mysql", "redis",
    "postgresql", "mongodb", "elasticsearch", "kafka", "rabbitmq", "docker",
    "kubernetes", "k8s", "aws", "aliyun", "linux", "git", "ci/cd", "jenkins",
    "flink", "spark", "hadoop", "hive", "pytorch", "tensorflow", "llm", "rag",
    "agent", "langchain", "langgraph", "fastapi", "flask", "django", "spring",
    "springboot", "react", "vue", "html", "css", "javascript", "typescript",
    "node.js", "nginx", "微服务", "分布式", "高并发",
]

# 学历等级：用于教育门槛判断
_EDU_LEVEL = {"博士": 5, "硕士": 4, "本科": 3, "大专": 2, "高中": 1}


def register_domain_tools(registry):
    """把应用层工具注册进 Agent。"""
    registry.tool(
        name="list_files",
        description="列出指定目录下的所有文件（name + path），用于发现简历和 JD 文件",
        arg_desc={"directory": "要扫描的目录路径，如 app/data 或 app/data/jds"},
    )(list_files)

    registry.tool(
        name="read_text_file",
        description="读取一个文本文件（.md/.txt/.json 等）的内容，自动处理 UTF-8/GBK 编码",
        arg_desc={"path": "文件路径", "max_chars": "最多读取的字符数，默认 8000，防止超大文件撑爆上下文"},
    )(read_text_file)

    registry.tool(
        name="compute_match",
        description=(
            "核心打分器：对「简历文本」与「一个岗位 JD 文本」做规则匹配，"
            "返回 JSON：技能重合度/年限/学历是否达标/各维度分数/总分/差距清单。"
            "所有结论必须有该工具的真实数据支撑"
        ),
        arg_desc={"resume_text": "简历全文", "jd_text": "岗位 JD 全文"},
    )(compute_match)

    registry.tool(
        name="write_file",
        description="把文本内容写入文件（自动创建父目录），用于保存最终匹配报告",
        arg_desc={"path": "输出文件路径", "content": "要写入的文件内容"},
    )(write_file)
    return registry


# ------------------------------------------------------------------ 实现

def list_files(directory: str) -> dict:
    if not os.path.isdir(directory):
        return {"error": f"目录不存在：{directory}"}
    files = []
    for name in sorted(os.listdir(directory)):
        p = os.path.join(directory, name)
        kind = "dir" if os.path.isdir(p) else "file"
        files.append({"name": name, "path": p.replace("\\", "/"), "type": kind})
    return {"directory": directory, "files": files}


def read_text_file(path: str, max_chars: int = 8000) -> dict:
    """读文件，UTF-8 失败自动回退 GBK（Windows 常见）。"""
    if not os.path.isfile(path):
        return {"error": f"文件不存在：{path}"}
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {"error": "无法识别文件编码"}
    truncated = len(text) > max_chars
    return {"path": path, "chars": len(text), "truncated": truncated,
            "content": text[:max_chars]}


def write_file(path: str, content: str) -> dict:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path, "chars": len(content)}


# ---------------- 规则打分器 ----------------

def _extract_skills(text: str) -> set:
    low = text.lower()
    return {s for s in SKILLS if s in low}


def _extract_years(text: str) -> List[int]:
    """提取所有 "N年" 数字。"""
    return [int(x) for x in re.findall(r"(\d+)\s*年", text)]


def _edu_level(text: str) -> int:
    level = 0
    for kw, lv in _EDU_LEVEL.items():
        if kw in text:
            level = max(level, lv)
    return level


def compute_match(resume_text: str, jd_text: str) -> dict:
    # 技能维度
    resume_skills = _extract_skills(resume_text)
    jd_skills = _extract_skills(jd_text)
    matched = resume_skills & jd_skills
    skill_coverage = round(len(matched) / len(jd_skills), 2) if jd_skills else 1.0
    gaps = sorted(jd_skills - resume_skills)

    # 年限维度：简历取最大经验，JD 取最低门槛
    resume_years = max(_extract_years(resume_text)) if _extract_years(resume_text) else 0
    jd_min_years = min(_extract_years(jd_text)) if _extract_years(jd_text) else 0
    years_ok = resume_years >= jd_min_years

    # 学历维度
    resume_edu = _edu_level(resume_text)
    jd_min_edu = _edu_level(jd_text) or 3  # JD 没提学历默认本科
    edu_ok = resume_edu >= jd_min_edu

    # 综合分（权重可调：技能 50 / 年限 25 / 学历 25）
    overall = round(skill_coverage * 50 + (100 if years_ok else 0) * 0.25 + (100 if edu_ok else 0) * 0.25, 1)

    return {
        "jd_skills": sorted(jd_skills),
        "resume_skills": sorted(resume_skills),
        "matched_skills": sorted(matched),
        "skill_coverage": skill_coverage,
        "gap_skills": gaps,
        "resume_years": resume_years,
        "jd_min_years": jd_min_years,
        "years_ok": years_ok,
        "resume_edu": max((k for k, v in _EDU_LEVEL.items() if v == resume_edu), default="未提及"),
        "jd_min_edu": max((k for k, v in _EDU_LEVEL.items() if v == jd_min_edu), default="本科"),
        "edu_ok": edu_ok,
        "dim_scores": {
            "技能匹配": round(skill_coverage * 100, 1),
            "经验年限": 100 if years_ok else 0,
            "学历门槛": 100 if edu_ok else 0,
        },
        "overall_score": overall,
        "verdict": "强烈推荐" if overall >= 80 else ("推荐" if overall >= 60 else "待定"),
    }