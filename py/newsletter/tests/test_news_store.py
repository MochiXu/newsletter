"""新闻语料库(v1.8 P1):月分区 / uuid 幂等 / JSON 字段 / 区间读取。"""

import tempfile
import unittest
from pathlib import Path

from newsletter.news.store import NewsStore, normalize_record


def _rec(uuid, pub, **kw):
    return {"uuid": uuid, "published_at": pub, "title": f"T-{uuid}", "source": "cnbc.com",
            "direction": "up", "sentiment_score": 0.5, "affected_assets": ["黄金"], **kw}


class TestNormalize(unittest.TestCase):
    def test_fills_columns_and_json(self):
        r = normalize_record({"uuid": "x1", "published_at": "2026-06-18T12:00:00", "affected_assets": ["黄金", "美元"]})
        self.assertEqual(r["source_tag"], "forward")  # 默认
        self.assertEqual(r["affected_assets"], '["黄金", "美元"]')  # list → JSON 串
        self.assertEqual(r["extra"], "{}")
        self.assertEqual(r["first_seen_date"], "2026-06-18")  # 从 published_at 推
        self.assertEqual(r["schema_version"], 1)


class TestStore(unittest.TestCase):
    def test_upsert_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            s = NewsStore(Path(d))
            n = s.upsert([_rec("a", "2026-06-17T10:00:00"), _rec("b", "2026-06-18T10:00:00")])
            self.assertEqual(n, 2)
            df = s.load()
            self.assertEqual(set(df["uuid"]), {"a", "b"})

    def test_uuid_idempotent_keep_last(self):
        with tempfile.TemporaryDirectory() as d:
            s = NewsStore(Path(d))
            s.upsert([_rec("a", "2026-06-18T10:00:00", sentiment_score=0.5)])
            s.upsert([_rec("a", "2026-06-18T10:00:00", sentiment_score=-0.9)])  # 重分析覆盖
            df = s.load()
            self.assertEqual(len(df), 1)  # 不重复
            self.assertAlmostEqual(float(df.iloc[0]["sentiment_score"]), -0.9)  # keep last

    def test_month_partition(self):
        with tempfile.TemporaryDirectory() as d:
            s = NewsStore(Path(d))
            s.upsert([_rec("a", "2026-05-30T10:00:00"), _rec("b", "2026-06-01T10:00:00")])
            self.assertTrue((Path(d) / "news-2026-05.parquet").exists())
            self.assertTrue((Path(d) / "news-2026-06.parquet").exists())

    def test_existing_uuids(self):
        with tempfile.TemporaryDirectory() as d:
            s = NewsStore(Path(d))
            s.upsert([_rec("a", "2026-06-18T10:00:00")])
            self.assertEqual(s.existing_uuids(["2026-06"]), {"a"})
            self.assertEqual(s.existing_uuids(["2026-05"]), set())

    def test_load_date_range(self):
        with tempfile.TemporaryDirectory() as d:
            s = NewsStore(Path(d))
            s.upsert([_rec("a", "2026-06-15T10:00:00"), _rec("b", "2026-06-18T10:00:00"),
                      _rec("c", "2026-06-22T10:00:00")])
            df = s.load(start="2026-06-16", end="2026-06-20")
            self.assertEqual(set(df["uuid"]), {"b"})

    def test_empty_load(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(NewsStore(Path(d)).load().empty)


if __name__ == "__main__":
    unittest.main()
