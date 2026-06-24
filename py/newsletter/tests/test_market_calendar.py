"""市场日历(v1.7):周末 / 节假日判定 + 区间日历(全离线)。"""

import unittest

from newsletter import market_calendar as mc


class TestNonTradingReason(unittest.TestCase):
    def test_weekend(self):
        self.assertEqual(mc.nontrading_reason("2026-06-20"), "weekend")  # 周六
        self.assertEqual(mc.nontrading_reason("2026-06-21"), "weekend")  # 周日

    def test_holiday(self):
        self.assertEqual(mc.nontrading_reason("2026-06-19"), "holiday")  # Juneteenth(周五)
        self.assertEqual(mc.nontrading_reason("2026-12-25"), "holiday")  # 圣诞

    def test_trading_day(self):
        self.assertIsNone(mc.nontrading_reason("2026-06-18"))  # 周四,交易日
        self.assertIsNone(mc.nontrading_reason("2026-06-22"))  # 周一,交易日

    def test_is_helpers(self):
        self.assertTrue(mc.is_weekend("2026-06-20"))
        self.assertFalse(mc.is_weekend("2026-06-18"))
        self.assertTrue(mc.is_holiday("2026-06-19"))
        self.assertFalse(mc.is_holiday("2026-06-18"))


class TestIterDays(unittest.TestCase):
    def test_range_inclusive(self):
        self.assertEqual(
            mc.iter_days("2026-06-18", "2026-06-22"),
            ["2026-06-18", "2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22"],
        )

    def test_single_day(self):
        self.assertEqual(mc.iter_days("2026-06-18", "2026-06-18"), ["2026-06-18"])

    def test_end_before_start_empty(self):
        self.assertEqual(mc.iter_days("2026-06-22", "2026-06-18"), [])


if __name__ == "__main__":
    unittest.main()
