"""features:交易日历/ffill、特征正确性、**因果性(不偷看未来)**。"""

import unittest

import numpy as np
import pandas as pd

from newsletter import features
from newsletter.sources.base import DATE, VALUE


def _long(series_id: str, dates, values) -> pd.DataFrame:
    return pd.DataFrame({DATE: [d.strftime("%Y-%m-%d") for d in dates], "series_id": series_id, VALUE: values})


class TestBuildWide(unittest.TestCase):
    def test_reindex_bdays_and_drop_weekend(self):
        # SP500 工作日;XAUUSD 含一个周六
        bdays = pd.bdate_range("2026-06-01", periods=5)  # 周一..周五
        sat = pd.Timestamp("2026-06-06")  # 周六
        long = pd.concat([
            _long("SP500", bdays, [100, 101, 102, 103, 104]),
            _long("XAUUSD", list(bdays) + [sat], [10, 11, 12, 13, 14, 99]),
        ])
        wide = features.build_wide(long)
        # 索引为工作日,周六被丢弃
        self.assertNotIn(sat, wide.index)
        self.assertEqual(len(wide.index), 5)

    def test_ffill_holiday_gap(self):
        # 缺一天(节假日)→ 前向填充
        days = [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-03")]  # 缺 06-02
        long = _long("SP500", days, [100, 102])
        wide = features.build_wide(long)
        self.assertAlmostEqual(wide.loc["2026-06-02", "SP500"], 100.0)  # ffill


class TestFeatureCorrectness(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2024-01-01", periods=300)

    def test_returns_and_ma(self):
        vals = [100 * (1.001**i) for i in range(300)]  # 每日 +0.1%
        feat = features.compute_features(features.build_wide(_long("SP500", self.dates, vals)))
        target = self.dates[290].strftime("%Y-%m-%d")
        snap = features.snapshot_at(feat, target)
        # 5 日收益 ≈ 1.001^5 - 1
        self.assertAlmostEqual(snap["SP500_ret_5"], 1.001**5 - 1, places=6)
        self.assertIn("SP500_ma_20", snap)
        self.assertGreater(snap["SP500_above_ma200"], 0.5)  # 单调上行,在 MA200 上方

    def test_rate_changes_bp(self):
        vals = [4.0 + 0.01 * i for i in range(300)]  # 每日 +1bp
        feat = features.compute_features(features.build_wide(_long("DGS10", self.dates, vals)))
        target = self.dates[290].strftime("%Y-%m-%d")
        snap = features.snapshot_at(feat, target)
        # 20 日变化 ≈ +20bp
        self.assertAlmostEqual(snap["DGS10_chg_20"], 20.0, places=4)

    def test_metric_level_change_uses_actual_obs(self):
        # 停更序列:相邻真实观测点的变化,而非 ffill 后的 0
        long = _long("DGS10", [pd.Timestamp("2026-06-10"), pd.Timestamp("2026-06-12")], [4.40, 4.48])
        lc = features.metric_level_change(long, "DGS10", "2026-06-18")
        self.assertIsNotNone(lc)
        level, change = lc
        self.assertAlmostEqual(level, 4.48)
        self.assertAlmostEqual(change, 0.08)  # 真实变动,非 0

    def test_metric_spark_tail_causal(self):
        # 取 <= target 的最近 n 个真实观测;不偷看未来
        dates = [pd.Timestamp("2026-06-10"), pd.Timestamp("2026-06-12"),
                 pd.Timestamp("2026-06-15"), pd.Timestamp("2026-06-20")]
        long = _long("DGS10", dates, [4.40, 4.42, 4.45, 4.50])
        spark = features.metric_spark(long, "DGS10", "2026-06-18", n=2)
        self.assertEqual(spark, [4.42, 4.45])  # 截到 06-18,最近2点,06-20 被排除


class TestCausality(unittest.TestCase):
    """红线:target_date 的特征绝不依赖其后任何数据。"""

    def test_no_lookahead(self):
        dates = pd.bdate_range("2024-01-01", periods=400)
        rng = np.random.default_rng(42)
        vals = 100 + np.cumsum(rng.normal(0, 1, 400))
        long = _long("SP500", dates, vals)
        target = dates[300].strftime("%Y-%m-%d")

        feat_full = features.compute_features(features.build_wide(long))
        # 截断到 <= target(删除未来),特征应完全一致
        long_cut = long[long[DATE] <= target]
        feat_cut = features.compute_features(features.build_wide(long_cut))

        a = features.snapshot_at(feat_full, target)
        b = features.snapshot_at(feat_cut, target)
        common = set(a) & set(b)
        self.assertGreater(len(common), 5)
        diffs = [k for k in common if abs(a[k] - b[k]) > 1e-9]
        self.assertEqual(diffs, [], f"特征偷看未来: {diffs}")


if __name__ == "__main__":
    unittest.main()
