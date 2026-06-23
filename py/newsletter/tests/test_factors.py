"""factors:因子合成 / kind 分支(DGS2 利率不触 px_vs_ma200)/ EWMA 波动 / 缺失容错。

因果性由 snap 继承(snap=features.snapshot_at,已在 test_features 守红线),factors 是其纯变换。
"""

import unittest

import pandas as pd

from newsletter import factors, features


class TestPriceFactors(unittest.TestCase):
    def test_composite_hand_calc(self):
        # 趋势 0.8、动量 0.5、价值 0.8(极端,反向计入):0.5*0.8 + 0.4*0.5 - 0.1*0.8 = 0.52
        snap = {
            "NASDAQCOM_px_vs_ma200": 0.08,  # /0.10 → 0.8
            "NASDAQCOM_ret_20": 0.05,  # /0.10 → 0.5
            "NASDAQCOM_rangepct_252": 0.9,  # (0.9-0.5)*2 → 0.8
            "NASDAQCOM_vol_ewma": 0.18,
        }
        af = factors.compute_factors(snap)["NASDAQCOM"]
        self.assertEqual(af.scores, {"trend": 0.8, "momentum": 0.5, "value": 0.8})
        self.assertAlmostEqual(af.composite, 0.52, places=4)
        self.assertEqual(af.baseline_dir, "up")
        self.assertAlmostEqual(af.baseline_conf, 0.76, places=4)  # 0.5 + min(0.45, 0.5*0.52)
        self.assertAlmostEqual(af.vol_forecast_ann, 0.18, places=4)

    def test_value_not_extreme_excluded(self):
        # 价值 0.4(<0.6 阈值)→ 不进合成:0.5*(-0.6) + 0.4*(-0.4) = -0.46 → down
        snap = {
            "NASDAQCOM_px_vs_ma200": -0.06,  # → -0.6
            "NASDAQCOM_ret_20": -0.04,  # → -0.4
            "NASDAQCOM_rangepct_252": 0.7,  # value 0.4(不极端)
        }
        af = factors.compute_factors(snap)["NASDAQCOM"]
        self.assertAlmostEqual(af.composite, -0.46, places=4)
        self.assertEqual(af.baseline_dir, "down")

    def test_clip_bounds(self):
        snap = {"XAUUSD_px_vs_ma200": 0.5, "XAUUSD_ret_20": 0.5}  # 远超标度 → 各 clip 到 1.0
        af = factors.compute_factors(snap)["XAUUSD"]
        self.assertEqual(af.scores["trend"], 1.0)
        self.assertEqual(af.scores["momentum"], 1.0)


class TestRateFactors(unittest.TestCase):
    def test_dgs2_uses_rate_branch_no_crash(self):
        # DGS2 是利率:只有 chg_*/z_*,没有 px_vs_ma200/ret_20/rangepct → 走利率分支,不报错
        snap = {
            "DGS2_chg_60": 25.0,  # /50 → 0.5
            "DGS2_chg_20": 15.0,  # /30 → 0.5
            "DGS2_z_252": 1.0,  # /2 → 0.5
        }
        af = factors.compute_factors(snap)["DGS2"]
        self.assertEqual(af.scores, {"trend": 0.5, "momentum": 0.5, "value": 0.5})
        self.assertAlmostEqual(af.composite, 0.45, places=4)  # 0.5*0.5 + 0.4*0.5(价值不极端)
        self.assertEqual(af.baseline_dir, "up")
        self.assertEqual(af.vol_forecast_ann, 0.0)  # 利率不出波动预测


class TestRosterAndDefaults(unittest.TestCase):
    def test_all_roster_assets(self):
        af = factors.compute_factors({})
        self.assertEqual(set(af), {"NASDAQCOM", "XAUUSD", "DTWEXBGS", "DGS2"})

    def test_empty_snap_is_flat(self):
        # 全缺失 → 各因子 0 → composite 0 → flat、信心 0.5、波动 0(不崩)
        af = factors.compute_factors({})["DTWEXBGS"]
        self.assertEqual(af.composite, 0.0)
        self.assertEqual(af.baseline_dir, "flat")
        self.assertAlmostEqual(af.baseline_conf, 0.5, places=4)


class TestEwmaVol(unittest.TestCase):
    def test_constant_return_converges(self):
        # 每日恒定 +1% → EWMA 年化波动 → |r|*sqrt(252) = 0.01*15.8745
        s = pd.Series([100 * (1.01**i) for i in range(300)])
        vol = features._vol_ewma(s)
        self.assertAlmostEqual(float(vol.iloc[-1]), 0.01 * (252**0.5), delta=0.005)

    def test_recent_spike_raises_forecast(self):
        calm = pd.Series([100 * (1.001**i) for i in range(200)])
        spiky = pd.concat([calm, pd.Series([100, 110, 95, 115, 90])], ignore_index=True)
        self.assertGreater(float(features._vol_ewma(spiky).iloc[-1]), float(features._vol_ewma(calm).iloc[-1]))


if __name__ == "__main__":
    unittest.main()
