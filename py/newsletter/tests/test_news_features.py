"""news.features:截面聚合(量/净情绪/分歧度/事件/EPU…)、入库记录、滚动时序、噪音排除、别名回填。"""

import json
import unittest

import pandas as pd

from newsletter.news.base import NewsItem
from newsletter.news.features import build_article_records, compute_news_features, compute_news_trends


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
        ev = self.f["events"]  # v1.8 事件分类法(monetary/inflation/jobs/geopolitical/...)
        self.assertTrue(ev["monetary"])    # "FOMC decision"
        self.assertTrue(ev["inflation"])   # "CPI inflation report"
        self.assertFalse(ev["jobs"])
        self.assertFalse(ev["geopolitical"])

    def test_v18_cross_sectional_signals(self):
        # v1.8:截面新增 EPU/GPR/不确定/类别构成 + 每资产分歧度
        self.assertIn("epu", self.f)
        self.assertIn("gpr", self.f)
        self.assertIn("categoryMix", self.f)
        self.assertIn("sentimentDispersion", self.f["byAsset"]["NASDAQCOM"])

    def test_headlines_capped(self):
        self.assertLessEqual(len(self.f["byAsset"]["NASDAQCOM"]["headlines"]), 3)

    def test_empty(self):
        f = compute_news_features([], None)
        self.assertEqual(f["total"], 0)
        self.assertEqual(f["byAsset"], {})


class TestArticleRecords(unittest.TestCase):
    def test_build_records_with_code_signals(self):
        items = [NewsItem(source="cnbc", title="Fed to hike rates amid policy uncertainty in the economy",
                          link="u1", uuid="x1", published="2026-06-18T10:00:00", asset="DGS2",
                          text="The Federal Reserve signaled it will hike and tighten. Economic uncertainty rose.")]
        recs = build_article_records(items, [{"index": 1, "direction": "up", "category": "解读",
                                              "sentiment": 0.4, "affected_assets": ["美债"]}], source_tag="forward")
        r = recs[0]
        self.assertEqual(r["uuid"], "x1")
        self.assertEqual(r["sentiment_score"], 0.4)
        self.assertIn("monetary", r["event_types"])  # 代码算事件
        self.assertEqual(r["extra"]["epu"], 1.0)      # 经济∧政策∧不确定
        self.assertGreater(r["hawkish_dovish"], 0)    # 偏鹰
        self.assertEqual(r["source_tag"], "forward")


class TestNewsTrends(unittest.TestCase):
    def test_rolling_from_corpus(self):
        # 构造语料库帧:黄金连续 6 天情绪走高
        rows = []
        for i, (day, s) in enumerate(zip(
                ["2026-06-10", "2026-06-11", "2026-06-12", "2026-06-15", "2026-06-16", "2026-06-17"],
                [-0.3, -0.1, 0.0, 0.2, 0.4, 0.6])):
            rows.append({"uuid": f"g{i}", "published_at": f"{day}T10:00:00",
                         "affected_assets": json.dumps(["XAUUSD"]), "sentiment_score": s})
        df = pd.DataFrame(rows)
        tr = compute_news_trends(df, "2026-06-17", windows=(5, 20))
        self.assertIn("XAUUSD", tr)
        self.assertIsNotNone(tr["XAUUSD"]["sentMean5"])
        self.assertGreater(tr["XAUUSD"]["sentMomentum"], 0)  # 情绪在走强 → 正动量

    def test_divergence(self):
        # 12 个交易日(足够 sentMean20 的 min_periods=10);情绪乐观(+0.6)但价格跌(-5%)→ 正背离
        days = pd.bdate_range("2026-06-01", periods=12).strftime("%Y-%m-%d")
        rows = [{"uuid": f"g{i}", "published_at": f"{d}T10:00:00",
                 "affected_assets": '["XAUUSD"]', "sentiment_score": 0.6} for i, d in enumerate(days)]
        df = pd.DataFrame(rows)
        tr = compute_news_trends(df, days[-1], windows=(5, 20), price_returns={"XAUUSD": -0.05})
        self.assertIsNotNone(tr["XAUUSD"]["divergence"])
        self.assertGreater(tr["XAUUSD"]["divergence"], 0)  # 情绪比价格乐观

    def test_empty_corpus(self):
        self.assertEqual(compute_news_trends(pd.DataFrame(), "2026-06-17"), {})


if __name__ == "__main__":
    unittest.main()
