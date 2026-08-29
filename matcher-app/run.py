"""命令行入口。

用法：
    python run.py                       # 正常模式：LLM Agent（需配置 API key）
    python run.py --mock                # Mock 模式：确定性规则管线，无需 key
    python run.py --resume app/data/sample_resume.md --jds app/data/jds --report reports/my.md
    python run.py --verbose             # 打印 Agent 每个步骤（强烈建议开）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import app.main as appmod
import config as cfg
from mini_agent.llm import LLMError

DEFAULT_RESUME = appmod.DATA_DIR / "sample_resume.md"
DEFAULT_JDS = appmod.JD_DIR
DEFAULT_REPORT = appmod.REPORT_DIR / "match_report.md"


def main():
    parser = argparse.ArgumentParser(description="简历×JD 匹配 Agent")
    parser.add_argument("--resume", default=str(DEFAULT_RESUME), help="简历文件路径")
    parser.add_argument("--jds", default=str(DEFAULT_JDS), help="JD 目录")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="报告输出路径")
    parser.add_argument("--mock", action="store_true", help="Mock 模式（无 LLM）")
    parser.add_argument("--verbose", action="store_true", help="打印 Agent 步骤")
    args = parser.parse_args()

    if args.mock or cfg.MOCK_MODE:
        if not args.mock and cfg.MOCK_MODE:
            print("[warn] 未检测到有效的 LLM_API_KEY，自动进入 Mock 模式（配置方法见 README）")
        result = appmod.run_mock_pipeline(args.resume, args.jds, args.report)
        print(result)
        return

    try:
        agent = appmod.build_agent(cfg)
    except Exception as e:
        print(f"[error] Agent 初始化失败（检查 key/base_url/model）：{e}")
        sys.exit(1)

    user_task = (
        f"请评估简历 {args.resume} 与目录 {args.jds} 下所有岗位的匹配度，"
        f"并生成报告保存到 {args.report}。"
        if args.verbose else
        f"评估简历 {args.resume} 与目录 {args.jds} 下所有岗位的匹配度，"
        f"生成报告保存到 {args.report}，并给出总结。"
    )

    try:
        answer = agent.run(user_task, verbose=args.verbose)
    except LLMError as e:
        print(f"[error] {e}")
        print("[hint] 检查网络与 API key 配置（config.py 或环境变量）后重试")
        sys.exit(1)

    print("\n================ 最终回答 ================")
    print(answer)
    print("==========================================")
    if Path(args.report).exists():
        print(f"[ok] 报告已保存：{args.report}")


if __name__ == "__main__":
    main()