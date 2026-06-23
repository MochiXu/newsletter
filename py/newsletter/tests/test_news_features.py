"""news.features(v1.6 S5c):每资产量/净情绪聚合、事件关键词、噪音排除、资产别名回填。"""

import unittest

from newsletter.news.base import NewsItem
from newsletter.news.features import compute_news_features


class TestNewsFeatures(unittest.TestCase):
    def setUp(self):
        self.items = [
            NewsItem(source="cnbc", title="Gold up ahead of FOMC decision", link="u1", asset="XAUUSD"),
            NewsItem(source="mw", title="Nasdaq slides on tech selloff", link="u2", asset="NASDAQCOM"),
            NewsItem(source="rss", title="Hot CPI inflation report", link="u3"),  # 无 asset,靠分类回填
            NewsItem(source="x", title="Sponsored ad", link="u4", asset="XAUUSD"),  # 噪音
        ]
        self.classified = [
            {"index": 1, "direction": "up", "category": "事实", "affected_assets": ["黄金"]},
            {"index": 2, "direction": "down", "category": "解读", "affected_assets": ["美股"]},
            {"index": 3, "direction": "down", "category": "解读", "affected_assets": ["美股"]},
            {"index": 4, "direction": "watch", "category": "噪音", "affected_assets": []},
        ]
        self.f = compute_news_features(self.items, self.classified)

    def test_noise_excluded_total(self):
        self.assertEqual(self.f["total"], 3)  # 噪音那条不计

    def test_per_asset_count_and_sentiment(self):
        ba = self.f["byAsset"]
        self.assertEqual(ba["XAUUSD"]["count"], 1)          # 仅 it1(噪音 it4 排除)
        self.assertEqual(ba["XAUUSD"]["netSentiment"], 1.0)  # up
        self.assertEqual(ba["NASDAQCOM"]["count"], 2)        # it2(asset)+it3(别名回填美股)
        self.assertEqual(ba["NASDAQCOM"]["netSentiment"], -1.0)  # down,down

    def test_event_flags(self):
        ev = self.f["events"]
        self.assertTrue(ev["fomc"])  # "FOMC decision"
        self.assertTrue(ev["cpi"])   # "CPI inflation report"
        self.assertFalse(ev["jobs"])
        self.assertFalse(ev["geo"])

    def test_headlines_capped(self):
        self.assertLessEqual(len(self.f["byAsset"]["NASDAQCOM"]["headlines"]), 3)

    def test_empty(self):
        f = compute_news_features([], None)
        self.assertEqual(f["total"], 0)
        self.assertEqual(f["byAsset"], {})


if __name__ == "__main__":
    unittest.main()
