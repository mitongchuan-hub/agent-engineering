"""评测集 Runner。

用法：
    python eval/run_eval.py               # 纯打分器回归（无需网络/key）
    python eval/run_eval.py -v            # 打印每个 case 明细
    python eval/run_eval.py --smoke       # 冒烟：跑一次完整管线（Mock 模式）
    python eval/run_eval.py --smoke --real# 冒烟：跑真 Agent（需要 key）

退出码：0=全部通过（可挂 CI），1=有失败。

测评维度（面试话术）：
    - 结论准确率（verdict accuracy）：分类任务的核心指标
    - 评分均误差（score MAE）：回归任务的粒度指标
    - 冒烟测试：端到端（读文件 -> 打分 -> 写报告）不崩
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.cases import CASES  # noqa: E402


def run_scorer_eval(verbose: bool = False):
    """在全部 case 上运行 compute_match 并与 oracle 比对。"""
    from app.tools import compute_match

    passed, total, abs_errors = 0, 0, []
    for case in CASES:
        total += 1
        r = compute_match(case["resume"], case["jd"])
        score, verdict = r["overall_score"], r["verdict"]
        oracle = case["oracle"]
        ok_score = oracle["min_score"] <= score <= oracle["max_score"]
        ok_verdict = oracle["verdict"] == verdict
        ok = ok_score and ok_verdict
        passed += ok
        if not ok_score:
            mid = (oracle["min_score"] + oracle["max_score"]) / 2
            abs_errors.append(abs(score - mid))
        if verbose or not ok:
            gap = ", ".join(g for g in r.get("gap_skills", [])[:3]) or "无"
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {case['name']}: score={score} (期望 "
                  f"{oracle['min_score']}~{oracle['max_score']}), "
                  f"verdict={verdict} (期望 {oracle['verdict']}), 缺口={gap}")

    accuracy = passed / total
    mae = (sum(abs_errors) / len(abs_errors)) if abs_errors else 0.0
    print("\n========== 评测汇总 ==========")
    print(f"  用例数       : {total}")
    print(f"  结论准确率   : {accuracy:.0%} ({passed}/{total})")
    print(f"  评分均误差   : {mae:.2f} 分")
    ok = accuracy >= 1.0
    print(f"  结果         : {'✅ 全部通过' if ok else '❌ 存在失败'}")
    return ok


def run_smoke(real: bool = False):
    """端到端冒烟：构造临时目录放置 case 文件，走完整管线产出报告。"""
    import config as cfg
    case = CASES[0]
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        resume_path = base / f"{case['name']}_resume.md"
        jds_dir = base / "jds"
        jds_dir.mkdir()
        resume_path.write_text(case["resume"], encoding="utf-8")
        (jds_dir / f"{case['name']}_jd.md").write_text(case["jd"], encoding="utf-8")
        report_path = base / "report.md"

        if real and not cfg.MOCK_MODE:
            from app.main import build_agent
            agent = build_agent(cfg)
            agent.run(f"评估简历 {resume_path} 与 {jds_dir} 下岗位的匹配度，"
                      f"生成报告保存到 {report_path}", verbose=True)
        else:
            from app.main import run_mock_pipeline
            print("  [smoke] 未配置 key 或未指定 --real，使用 Mock 管线")
            run_mock_pipeline(resume_path, jds_dir, report_path)

        ok = report_path.exists() and report_path.stat().st_size > 50
        print(f"\n  [smoke] 端到端管线 {'✅ 通过' if ok else '❌ 失败'}，报告：{report_path}")
        return ok


def main():
    ap = argparse.ArgumentParser(description="简历匹配 Agent 评测集")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个 case 明细")
    ap.add_argument("--smoke", action="store_true", help="额外跑一次端到端冒烟")
    ap.add_argument("--real", action="store_true", help="冒烟用真 Agent（需 key）")
    args = ap.parse_args()

    ok = run_scorer_eval(verbose=args.verbose)
    if args.smoke:
        ok = run_smoke(real=args.real) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()