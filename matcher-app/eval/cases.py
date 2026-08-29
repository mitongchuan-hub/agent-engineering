"""评测集用例（Oracle 测试）：简历×JD 文本 + 期望结论。

每个 case 的 oracle 用「得分区间 + 结论」定义：
    min_score / max_score  期望的 compute_match 总分范围（容忍打分器小幅调整）
    verdict               期望结论（待定 < 60 / 推荐 60-80 / 强烈推荐 ≥ 80）

这是「规则打分器的回归测试」：以后谁改了 compute_match 的权重/词表，
跑一遍 eval 就知道打分行为有没有跑偏。
"""
from __future__ import annotations

CASES = [
    {
        "name": "case_backend_full",
        "note": "后端正岗：技能/年限/学历全达标 → 满分",
        "resume": "3 年经验，硕士，Java Spring Boot MySQL Redis Kafka Docker Kubernetes 分布式 高并发 微服务",
        "jd":     "要求 3 年以上，本科及以上，Java Spring Boot MySQL Redis Kafka Docker Kubernetes 分布式 高并发 微服务",
        "oracle": {"verdict": "强烈推荐", "min_score": 95, "max_score": 100},
    },
    {
        "name": "case_ai_missing_es",
        "note": "AI 岗：技能 5/6 覆盖、年限学历达标 → 高分但不满分（缺口 Elasticsearch）",
        "resume": "2 年经验，硕士，Python LLM RAG Agent LangChain",
        "jd":     "要求 1 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch",
        "oracle": {"verdict": "强烈推荐", "min_score": 85, "max_score": 95},
    },
    {
        "name": "case_ai_low_edu",
        "note": "AI 岗：技能 5/6 覆盖、年限够，但本科不满足硕士底线 → 降档为推荐",
        "resume": "2 年经验，本科，Python LLM RAG Agent LangChain",
        "jd":     "要求 1 年以上，硕士及以上，Python LLM RAG Agent LangChain Elasticsearch",
        "oracle": {"verdict": "推荐", "min_score": 60, "max_score": 75},
    },
    {
        "name": "case_junior_no_match",
        "note": "应届生投 5 年经验后端岗：无年限、技能零重合 → 待定",
        "resume": "应届毕业生，本科，前端 HTML CSS JavaScript 课程设计",
        "jd":     "要求 5 年以上，本科及以上，Python Java 分布式 高并发",
        "oracle": {"verdict": "待定", "min_score": 0, "max_score": 40},
    },
    {
        "name": "case_years_fail",
        "note": "技能/学历全达标但年限 1 < 3 → 被年限卡掉 25 分",
        "resume": "1 年经验，硕士，Python RAG Agent",
        "jd":     "要求 3 年以上，硕士及以上，Python RAG Agent",
        "oracle": {"verdict": "推荐", "min_score": 70, "max_score": 80},
    },
    {
        "name": "case_frontend_mismatch",
        "note": "5 年前端转投 Java 后端：年限学历够但技能零重合 → 待定（技能权重最高）",
        "resume": "5 年经验，本科，前端 React Vue HTML",
        "jd":     "要求 3 年以上，本科及以上，Java Spring MySQL 分布式 高并发",
        "oracle": {"verdict": "待定", "min_score": 45, "max_score": 55},
    },
]


def get_case(name: str):
    for c in CASES:
        if c["name"] == name:
            return c
    raise KeyError(name)