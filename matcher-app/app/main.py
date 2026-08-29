"""应用组装：系统提示词 + Agent 装配 + Mock（无 key）管线。

面试可讲：
    - 这里的 system prompt 本质是「工作流编排」——告诉模型先做什么后做什么
    - Mock 管线用确定性代码复刻同一工作流：用于无 key 环境下的联调/CI/回归测试
"""
from __future__ import annotations

import os
from pathlib import Path

from mini_agent.agent import Agent
from mini_agent.llm import ChatClient
from mini_agent.tools import ToolRegistry

from app.tools import compute_match, list_files, read_text_file, register_domain_tools, write_file

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JD_DIR = DATA_DIR / "jds"
REPORT_DIR = BASE_DIR.parent / "reports"

SYSTEM_PROMPT = """你是一名资深的 HR 技术招聘顾问，负责为候选人做「简历 × 岗位 JD」匹配评估。

你的工作流程（务必按顺序执行）：
1. 调用 list_files 查看简历与 JD 所在目录有哪些文件
2. 调用 read_text_file 读取候选人的简历文件
3. 遍历每一个 JD 文件：先 read_text_file 读取，再调用 compute_match(resume_text, jd_text)
   获取量化的技能重合度、年限、学历、总分数据
4. 基于所有工具的**真实返回数据**，用中文写一份 Markdown 匹配报告，包含：
   - 候选人概览（从简历总结）
   - 每个岗位的匹配明细表：总分、技能覆盖率、缺口技能、年限/学历是否达标
   - 最匹配岗位分析 + 候选人短板与补强建议（每条建议都要对应具体缺口技能）
5. 调用 write_file 把报告保存到 reports/match_report.md
6. 最后给出 3~5 句中文总结

铁律：
- 所有分数、技能、结论必须来自工具的真实输出，禁止编造
- 报告要专业、结构化，用 Markdown 表格与标题
"""


def build_agent(cfg) -> Agent:
    registry = ToolRegistry()
    register_domain_tools(registry)
    llm = ChatClient(base_url=cfg.LLM_BASE_URL, api_key=cfg.LLM_API_KEY,
                     model=cfg.LLM_MODEL, temperature=cfg.TEMPERATURE,
                     extra_body=cfg.EXTRA_LLM_PARAMS)
    return Agent(llm=llm, registry=registry, system_prompt=SYSTEM_PROMPT,
                 max_iters=cfg.MAX_AGENT_ITERS, char_budget=cfg.CONTEXT_CHAR_BUDGET)


def run_mock_pipeline(resume_path: str | os.PathLike, jds_dir: str | os.PathLike,
                      report_path: str | os.PathLike) -> str:
    """Mock 模式：不依赖 LLM 的确定性管线，用于先跑通全流程。"""
    res = read_text_file(str(resume_path))
    resume_text = res.get("content", "")
    lines = [f"# 简历 × JD 匹配报告（Mock 模式，无 LLM）\n",
             f"> 简历：{resume_path}\n", f"> 岗位：{jds_dir}\n\n"]
    rows = []
    for jd in sorted(Path(jds_dir).glob("*.md")):
        r = compute_match(resume_text, read_text_file(str(jd))["content"])
        rows.append((jd.stem, r))
        lines.append(f"\n## {jd.stem}\n")
        lines.append(f"- 总分：**{r['overall_score']}**（{r['verdict']}）")
        lines.append(f"- 技能覆盖率：{r['skill_coverage'] * 100:.0f}%  匹配技能：{', '.join(r['matched_skills']) or '无'}")
        lines.append(f"- 缺口技能：{', '.join(r['gap_skills']) or '无'}")
        lines.append(f"- 年限：简历 {r['resume_years']} 年 vs 要求 {r['jd_min_years']} 年 → {'达标' if r['years_ok'] else '不达标'}")
        lines.append(f"- 学历：简历 {r['resume_edu']} vs 要求 {r['jd_min_edu']} → {'达标' if r['edu_ok'] else '不达标'}")
    write_file(str(report_path), "\n".join(lines))
    rows.sort(key=lambda x: -x[1]["overall_score"])
    best = rows[0]
    return (f"Mock 完成。共评估 {len(rows)} 个岗位，报告已保存到 {report_path}\n"
            f"最匹配：{best[0]}（总分 {best[1]['overall_score']}，{best[1]['verdict']}）")