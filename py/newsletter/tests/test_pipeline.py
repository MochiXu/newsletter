"""pipeline 新闻时间窗 / 防先知泄漏(v1.6 修复):历史日 live→backfill 自动降级。"""

import unittest
from unittest import mock

from newsletter import pipeline as pl


class TestEffectiveNewsMode(unittest.TestCase):
    """历史 target_date 跑 live 会抓到运行日(未来)新闻 → 必须自动降级 backfill。"""

    def setUp(self):
        self._patch = mock.patch.object(pl, "_today", return_value="2026-06-24")
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_past_date_live_downgrades_to_backfill(self):
        self.assertEqual(pl._effective_news_mode("live", "2026-06-18"), "backfill")

    def test_today_live_stays_live(self):
        self.assertEqual(pl._effective_news_mode("live", "2026-06-24"), "live")

    def test_future_date_live_stays_live(self):
        # 未来日(理论上不该发生)按 live,无未来新闻可泄
        self.assertEqual(pl._effective_news_mode("live", "2026-07-01"), "live")

    def test_none_unchanged(self):
        self.assertEqual(pl._effective_news_mode("none", "2026-06-18"), "none")

    def test_backfill_unchanged(self):
        self.assertEqual(pl._effective_news_mode("backfill", "2026-06-18"), "backfill")


class TestNewsWindow(unittest.TestCase):
    """backfill 时间窗 = [回放日-3天, 回放日];live/none 无窗(None,None)。"""

    def test_backfill_window(self):
        start, end = pl._news_window("2026-06-18", "backfill")
        self.assertEqual(start, "2026-06-15")
        self.assertEqual(end, "2026-06-18")  # published_before 实测排他,不含当天

    def test_live_no_window(self):
        self.assertEqual(pl._news_window("2026-06-18", "live"), (None, None))

    def test_none_no_window(self):
        self.assertEqual(pl._news_window("2026-06-18", "none"), (None, None))


if __name__ == "__main__":
    unittest.main()
