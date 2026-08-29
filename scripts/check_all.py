#!/usr/bin/env python3
"""一键回归：验证全部教学步骤可运行 + 应用单测与评测集通过。

用法（仓库根目录）：
    python scripts/check_all.py

流程：
    ① 35 个教学 code.py（learn-mini-agent s01~s10 + 三家机制重建 21 步）
       —— 演示模式逐个跑，断言退出码 0
    ② matcher-app：15 个单测（unittest）
    ③ matcher-app：评测集 6 个 Oracle 用例（exit=0 可挂 CI）

解释器：教学步骤用当前 python（无需依赖）；应用部分优先用 .venv，
        否则回退当前 python（此时需已安装 openai）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list, label: str) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        ok = r.returncode == 0
        tail = (r.stdout or r.stderr).strip().splitlines()
        tail = " / ".join(tail[-2:])[:100] if tail else ""
        print(f"  {'✅' if ok else '❌'} {label}" + (f"  [{tail}]" if tail else ""))
        return ok
    except Exception as e:
        print(f"  ❌ {label}  [异常: {type(e).__name__}]")
        return False


def check_teaching() -> tuple:
    """跑全部教学 code.py（演示模式，跳过真实 LLM 分支）。"""
    steps = []
    for base in ("learn-mini-agent", "agent-source/codex_learn",
                 "agent-source/deepseek_learn", "agent-source/pi_learn"):
        for f in sorted((ROOT / base).glob("*/code.py")):
            steps.append(f)
    print(f"① 教学步骤：{len(steps)} 个\n")
    passed = 0
    for f in steps:
        label = str(f.relative_to(ROOT)).replace("\\", "/")
        # 演示模式：清掉 API key 环境变量，强制走演示分支
        env = dict((k, v) for k, v in __import__("os").environ.items()
                   if k != "LLM_API_KEY")
        try:
            r = subprocess.run([sys.executable, str(f)],
                               cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=180)
            ok = r.returncode == 0
            passed += ok
            print(f"  {'✅' if ok else '❌'} {label}"
                  + ("" if ok else f"\n      {(r.stderr or r.stdout)[-300:]}"))
        except Exception as e:
            print(f"  ❌ {label}  [异常: {type(e).__name__}]")
    print(f"\n  教学步骤通过 {passed}/{len(steps)}\n")
    return passed == len(steps)


def check_app() -> bool:
    """应用单测 + 评测集。优先用 .venv 解释器。"""
    venv_py = ROOT / "matcher-app" / ".venv" / "Scripts" / "python.exe"
    py = str(venv_py) if venv_py.is_file() else sys.executable
    print("② 应用单测（unittest）")
    ok1 = _run([py, "-m", "unittest", "discover", "-s",
                str(ROOT / "matcher-app" / "tests")], "matcher-app/tests")
    print("\n③ 评测集（Oracle 用例）")
    ok2 = _run([py, str(ROOT / "matcher-app" / "eval" / "run_eval.py")],
               "matcher-app/eval/run_eval.py")
    print()
    return ok1 and ok2


if __name__ == "__main__":
    print("=" * 58)
    print(" Agent Harness 学习仓库 · 一键回归")
    print("=" * 58 + "\n")
    a = check_teaching()
    b = check_app()
    print("=" * 58)
    print(f" 结果：{'✅ 全部通过' if (a and b) else '❌ 存在失败'}")
    print("=" * 58)
    sys.exit(0 if (a and b) else 1)