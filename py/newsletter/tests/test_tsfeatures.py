"""共享时序工具箱(P0):算子正确性 + 短序列/NaN 健壮。"""

import math
import unittest

import pandas as pd

from newsletter import tsfeatures as ts


def _s(vals):
    return pd.Series(vals, dtype="float64")


class TestOperators(unittest.TestCase):
    def test_momentum(self):
        out = ts.momentum(_s([1, 2, 4, 7]), 1).tolist()
        self.assertTrue(math.isnan(out[0]))
        self.assertEqual(out[1:], [1.0, 2.0, 3.0])

    def test_acceleration(self):
        # 等差(动量恒定)→ 加速度 0;等比/加速 → 正
        lin = ts.acceleration(_s([0, 1, 2, 3, 4, 5]), 1).dropna().tolist()
        self.assertTrue(all(abs(x) < 1e-9 for x in lin))  # 匀速 → 加速度 0
        acc = ts.acceleration(_s([0, 1, 3, 6, 10, 15]), 1).dropna().tolist()
        self.assertTrue(all(x > 0 for x in acc))  # 动量递增 → 正加速度

    def test_zscore(self):
        z = ts.zscore(_s([10, 10, 10, 10, 20]), 5)
        self.assertGreater(z.iloc[-1], 0)  # 末值远高于均值 → 正 z
        flat = ts.zscore(_s([5, 5, 5, 5, 5]), 5)
        self.assertTrue(math.isnan(flat.iloc[-1]))  # std=0 → NaN(不爆)

    def test_slope(self):
        up = ts.slope(_s([0, 1, 2, 3, 4]), 5).iloc[-1]
        self.assertAlmostEqual(up, 1.0, places=6)  # 斜率 1
        down = ts.slope(_s([4, 3, 2, 1, 0]), 5).iloc[-1]
        self.assertAlmostEqual(down, -1.0, places=6)

    def test_reversal_flag(self):
        r = ts.reversal_flag(_s([1, 1, -1, -1, 1])).tolist()
        self.assertEqual(r, [0.0, 0.0, 1.0, 0.0, 1.0])  # 第3、5 个翻转

    def test_streak(self):
        st = ts.streak(_s([1, 2, 3, -1, -2, 5])).tolist()
        self.assertEqual(st, [1.0, 2.0, 3.0, -1.0, -2.0, 1.0])

    def test_dispersion(self):
        self.assertIsNone(ts.dispersion([1.0]))  # <2 → None
        self.assertAlmostEqual(ts.dispersion([1, 1, 1]), 0.0)
        self.assertGreater(ts.dispersion([0, 10]), 0)
        self.assertIsNone(ts.dispersion([None, float("nan")]))  # 无有效值


class TestScalarHelpers(unittest.TestCase):
    def test_last_helpers(self):
        s = _s([0, 1, 2, 3, 4])
        self.assertAlmostEqual(ts.last_slope(s, 5), 1.0, places=6)
        self.assertEqual(ts.last_streak(s), 4.0)  # 连涨 4 期(首期 NaN momentum 不适用,这里 s 本身)

    def test_short_series_no_crash(self):
        s = _s([1.0])
        self.assertIsNone(ts.last_acceleration(s, 20))  # 太短 → None,不抛
        self.assertIsNone(ts.last_zscore(s, 252))


if __name__ == "__main__":
    unittest.main()
