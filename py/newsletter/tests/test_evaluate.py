"""evaluate:技能 vs 基线 / 校准分桶 / Brier(手算核对)/ 动量 / _factor 选手 / 老行容错 / 落盘。"""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from newsletter import evaluate
from newsletter.config import Paths
from newsletter.sources.base import DATE, VALUE


def _row(created, model, asset, horizon, direction, realized, conf, base_dir="", base_conf=None):
    return {
        "created_date": created, "model": model, "asset": asset, "horizon": horizon,
        "direction": direction, "confidence": f"{conf:.4f}", "status": "settled",
        "resolved_date": created, "realized_dir": realized, "realized_text": "", "hit": "", "note": "",
        "base_dir": base_dir, "base_conf": (f"{base_conf:.4f}" if base_conf is not None else ""),
    }


# 4 条 NASDAQCOM/h_5d:命中 up,up,down,up vs 实际 up,down,down,up → 3/4 命中
def _rows():
    return [
        _row("2026-06-01", "m1", "NASDAQCOM", "h_5d", "up", "up", 0.70, "up", 0.70),
        _row("2026-06-02", "m1", "NASDAQCOM", "h_5d", "up", "down", 0.60, "down", 0.60),
        _row("2026-06-03", "m1", "NASDAQCOM", "h_5d", "down", "down", 0.55, "down", 0.55),
        _row("2026-06-04", "m1", "NASDAQCOM", "h_5d", "up", "up", 0.80, "up", 0.80),
    ]


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.sc = evaluate.score(_rows(), long_df=None)
        self.cell = self.sc["models"]["m1"]["byAsset"]["NASDAQCOM"]["h_5d"]

    def test_hit_and_drift_baseline(self):
        self.assertEqual(self.cell["hit"], 0.75)  # 3/4
        # 实际方向 up,down,down,up → 多数占比 2/4
        self.assertEqual(self.cell["driftBaseline"], 0.5)

    def test_factor_baseline_and_skill(self):
        # base_dir up,down,down,up vs 实际 up,down,down,up → 4/4 全中
        self.assertEqual(self.cell["factorBaseline"], 1.0)
        # 无 long_df → 动量 None;基线 = max(漂移0.5, 因子1.0)=1.0 → skill = 0.75-1.0
        self.assertIsNone(self.cell["momentumBaseline"])
        self.assertAlmostEqual(self.cell["skill"], -0.25, places=4)

    def test_brier_hand_calc(self):
        # (0.7-1)²+(0.6-0)²+(0.55-1)²+(0.8-1)² = 0.09+0.36+0.2025+0.04 = 0.6925 → /4
        self.assertAlmostEqual(self.cell["brier"], 0.173125, places=4)
        # climatology:p=0.75 → mean((0.75-h)²) = (0.0625*3+0.5625)/4 = 0.1875
        self.assertAlmostEqual(self.cell["brierBaseline"], 0.1875, places=4)

    def test_calibration_buckets(self):
        cal = {(b["lo"], b["hi"]): b for b in self.sc["models"]["m1"]["calibration"]}
        b1, b2, b3 = cal[(0.0, 0.6)], cal[(0.6, 0.75)], cal[(0.75, 1.01)]
        self.assertEqual((b1["n"], b1["stated"], b1["realized"]), (1, 0.55, 1.0))  # r3
        self.assertEqual((b2["n"], b2["stated"], b2["realized"]), (2, 0.65, 0.5))  # r1,r2
        self.assertEqual((b3["n"], b3["stated"], b3["realized"]), (1, 0.8, 1.0))  # r4

    def test_factor_contestant(self):
        f = self.sc["models"]["_factor"]
        self.assertEqual(f["overall"]["hit"], 1.0)  # base_dir 全中
        # _factor 不拿自己当基线
        self.assertIsNone(f["byAsset"]["NASDAQCOM"]["h_5d"]["factorBaseline"])


class TestMomentumBaseline(unittest.TestCase):
    def test_trailing_dir_from_history(self):
        dates = pd.bdate_range("2026-06-01", periods=12)
        long = pd.DataFrame({
            DATE: [d.strftime("%Y-%m-%d") for d in dates],
            "series_id": "NASDAQCOM",
            VALUE: [100 + i for i in range(12)],  # 单调上行
        })
        created = dates[-1].strftime("%Y-%m-%d")
        rows = [_row(created, "m1", "NASDAQCOM", "h_5d", "up", "up", 0.7, "up", 0.7)]
        cell = evaluate.score(rows, long)["models"]["m1"]["byAsset"]["NASDAQCOM"]["h_5d"]
        self.assertEqual(cell["momentumBaseline"], 1.0)  # 回看5日上行→预测up→实际up→命中


class TestRobustness(unittest.TestCase):
    def test_old_rows_without_base_dir(self):
        # 老行无 base_dir → 因子基线跳过(None),仍算漂移;不崩、无 _factor
        rows = [
            _row("2026-06-01", "m1", "XAUUSD", "h_5d", "up", "up", 0.7),
            _row("2026-06-02", "m1", "XAUUSD", "h_5d", "down", "up", 0.6),
        ]
        sc = evaluate.score(rows, long_df=None)
        cell = sc["models"]["m1"]["byAsset"]["XAUUSD"]["h_5d"]
        self.assertIsNone(cell["factorBaseline"])
        self.assertEqual(cell["hit"], 0.5)
        self.assertNotIn("_factor", sc["models"])

    def test_empty_settled(self):
        sc = evaluate.score([{"status": "pending"}], long_df=None)
        self.assertEqual(sc["models"], {})
        self.assertEqual(sc["asOf"], "")


class TestWriteScorecard(unittest.TestCase):
    def test_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            sc = evaluate.write_scorecard(_rows(), long_df=None, paths=paths)
            self.assertTrue(paths.scorecard_json.exists())
            self.assertTrue(paths.scorecard_md.exists())
            loaded = json.loads(paths.scorecard_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["source"], "forward")
            self.assertIn("m1", loaded["models"])
            self.assertIn("# 预测评估", paths.scorecard_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
