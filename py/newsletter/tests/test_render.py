"""render:契约组装、新闻分类映射、复盘、briefs.json upsert(刊号重算)。"""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from newsletter import render
from newsletter.config import Paths
from newsletter.models import Brief, Dir, LLMBrief, NewsCat, ReviewStatus, Tone


class TestBuildMetrics(unittest.TestCase):
    def test_metrics_from_actual_obs(self):
        long = pd.DataFrame({
            "date": ["2026-06-12", "2026-06-15"],
            "series_id": ["DGS10", "DGS10"],
            "value": [4.40, 4.47],
            "source": ["fred", "fred"],
        })
        metrics = render.build_metrics(long, "2026-06-18")
        m = next(x for x in metrics if x.key == "dgs10")
        self.assertAlmostEqual(m.value, 4.47)
        self.assertAlmostEqual(m.change, 0.07)
        self.assertEqual(m.kind.value, "yield")


class TestBuildNews(unittest.TestCase):
    def test_cat_mapping_filter_noise_and_nolink(self):
        merged = [
            {"source": "Fed", "title": "T1", "category": "事实", "affected_assets": ["美债"], "direction": "up", "link": "u1"},
            {"source": "CNBC", "title": "T2", "direction": "bad", "link": "u2"},  # 未分类 + 非法 dir → watch
            {"source": "MW", "title": "T3", "category": "噪音", "direction": "down", "link": "u3"},  # 噪音 → 丢弃
            {"source": "X", "title": "T4", "category": "事实", "link": ""},  # 无链接 → 丢弃
        ]
        news = render.build_news(merged)
        self.assertEqual([n.title for n in news], ["T1", "T2"])  # 噪音/无链接被过滤掉
        self.assertEqual(news[0].cat, NewsCat.FACT)
        self.assertEqual(news[0].dir, Dir.UP)
        self.assertIsNone(news[1].cat)  # 未分类
        self.assertEqual(news[1].dir, Dir.WATCH)  # 非法 dir → watch


class TestBuildReviews(unittest.TestCase):
    def test_resolved_today_first_then_open(self):
        rows = [
            {"if_then": "A", "status": "open"},
            {"if_then": "B", "status": "held", "resolved_date": "2026-06-18", "note": "n"},
            {"if_then": "C", "status": "invalidated", "resolved_date": "2026-06-01"},  # 往日定结,不计
        ]
        reviews = render.build_reviews(rows, "2026-06-18")
        self.assertEqual(reviews[0].status, ReviewStatus.HELD)  # 今日定结在前
        self.assertEqual(reviews[1].status, ReviewStatus.OPEN)
        self.assertEqual(len(reviews), 2)


class TestBuildBrief(unittest.TestCase):
    def test_degraded_when_llm_none(self):
        br = render.build_brief("2026-06-18", None, [], [], [])
        self.assertEqual(br.tone, Tone.NEUTRAL)
        self.assertEqual(br.facts, [])
        self.assertEqual(br.weekday, "周四")

    def test_full_from_llm(self):
        llm = LLMBrief(headline="H", tone="risk_on", facts=["f1"], interpretation=["i1"],
                       hypotheses=[{"if_then": "x", "invalidation": "z"}],
                       impact=[{"asset": "金", "watch": "w", "direction": "down"}])
        br = render.build_brief("2026-06-18", llm, [], [], [])
        self.assertEqual(br.tone, Tone.RISK_ON)
        self.assertEqual(br.hypotheses[0].if_then, "x")
        self.assertEqual(br.impacts[0].dir, Dir.DOWN)


class TestBriefsJson(unittest.TestCase):
    def test_upsert_and_issue_recompute(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            render.upsert_briefs_json(paths, Brief(date="2026-06-17", weekday="周三"), "DeepSeek")
            n = render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四"), "DeepSeek")
            self.assertEqual(n, 2)
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            self.assertEqual([b["date"] for b in data["briefs"]], ["2026-06-18", "2026-06-17"])  # 倒序
            issues = {b["date"]: b["issue"] for b in data["briefs"]}
            self.assertEqual(issues["2026-06-17"], 1)  # 最早 = 第 1 刊
            self.assertEqual(issues["2026-06-18"], 2)
            self.assertTrue((paths.briefs / "2026-06-18.json").exists())

    def test_upsert_same_date_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四", headline="old"), "M")
            render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四", headline="new"), "M")
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            self.assertEqual(len(data["briefs"]), 1)
            self.assertEqual(data["briefs"][0]["headline"], "new")


class TestMarkdown(unittest.TestCase):
    def test_markdown_smoke(self):
        llm = LLMBrief(headline="H", facts=["事实1"], interpretation=["判断1"])
        br = render.build_brief("2026-06-18", llm, [], [], [])
        md = render.render_markdown(br, macro=[{"label": "失业率", "value": 4.3, "obs_date": "2026-05-01"}])
        self.assertIn("每日宏观简报 · 2026-06-18", md)
        self.assertIn("事实1", md)
        self.assertIn("失业率", md)
        self.assertIn("不构成投资建议", md)


if __name__ == "__main__":
    unittest.main()
