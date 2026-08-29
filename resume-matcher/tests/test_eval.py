"""评测集回归测试：用例必须全部通过（作为 CI 的一部分防打分器跑偏）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eval.run_eval import run_scorer_eval  # noqa: E402


class TestEvalSuite(unittest.TestCase):
    def test_scorer_passes_all_oracles(self):
        ok = run_scorer_eval(verbose=False)
        self.assertTrue(ok, "打分器评测未全部通过——请检查 Compute了 eval/cases.py 的 oracle")


if __name__ == "__main__":
    unittest.main(verbosity=2)