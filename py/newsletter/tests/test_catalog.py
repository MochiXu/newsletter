"""catalog:兜底链(主源失败才降级)+ 整批组装。"""

import unittest

import pandas as pd

from newsletter import catalog
from newsletter.sources.base import FetchError


class _Ok:
    def __init__(self, last_val):
        self.calls = 0
        self._df = pd.DataFrame({"date": ["2026-06-12", "2026-06-13"], "value": [1.0, last_val]})

    def fetch(self, symbol, start=None, end=None):
        self.calls += 1
        return self._df


class _Fail:
    def __init__(self):
        self.calls = 0

    def fetch(self, symbol, start=None, end=None):
        self.calls += 1
        raise FetchError("down")


class _Empty:
    def fetch(self, symbol, start=None, end=None):
        return pd.DataFrame(columns=["date", "value"])


class TestFallback(unittest.TestCase):
    def test_primary_used_when_ok(self):
        spec = catalog.SeriesSpec("X", "x", catalog.KIND_INDEX,
                                  (catalog.SourceRef("a", "SYM"), catalog.SourceRef("b", "SYM2")))
        a, b = _Ok(9.0), _Ok(8.0)
        res = catalog.fetch_series(spec, {"a": a, "b": b}, None, None)
        self.assertIsNotNone(res)
        df, used = res
        self.assertEqual(used, "a")
        self.assertEqual(b.calls, 0)  # 主源成功,不碰兜底

    def test_degrade_after_primary_fails(self):
        spec = catalog.SeriesSpec("X", "x", catalog.KIND_INDEX,
                                  (catalog.SourceRef("a", "S"), catalog.SourceRef("b", "S2")))
        a, b = _Fail(), _Ok(7.0)
        df, used = catalog.fetch_series(spec, {"a": a, "b": b}, None, None)
        self.assertEqual(used, "b")
        self.assertEqual(a.calls, 1)

    def test_empty_treated_as_fail(self):
        spec = catalog.SeriesSpec("X", "x", catalog.KIND_INDEX,
                                  (catalog.SourceRef("a", "S"), catalog.SourceRef("b", "S2")))
        df, used = catalog.fetch_series(spec, {"a": _Empty(), "b": _Ok(5.0)}, None, None)
        self.assertEqual(used, "b")

    def test_all_fail_returns_none(self):
        spec = catalog.SeriesSpec("X", "x", catalog.KIND_INDEX, (catalog.SourceRef("a", "S"),))
        self.assertIsNone(catalog.fetch_series(spec, {"a": _Fail()}, None, None))

    def test_fetch_all_assembles_tidy(self):
        specs = (
            catalog.SeriesSpec("AA", "aa", catalog.KIND_INDEX, (catalog.SourceRef("a", "S"),)),
            catalog.SeriesSpec("BB", "bb", catalog.KIND_RATE, (catalog.SourceRef("a", "S"),)),
        )
        df = catalog.fetch_all({"a": _Ok(3.0)}, None, None, specs=specs)
        self.assertEqual(list(df.columns), ["date", "series_id", "value", "source"])
        self.assertEqual(set(df["series_id"]), {"AA", "BB"})
        self.assertTrue((df["source"] == "a").all())


class TestCatalogIntegrity(unittest.TestCase):
    def test_display_metrics_subset_of_catalog(self):
        self.assertTrue(set(s.series_id for s in catalog.DISPLAY_METRICS) <= set(catalog.SPEC_BY_ID))

    def test_daily_excludes_macro(self):
        self.assertNotIn("CPILFESL", catalog.DAILY_IDS)
        self.assertIn("CPILFESL", catalog.MACRO_IDS)
        self.assertIn("SP500", catalog.DAILY_IDS)


if __name__ == "__main__":
    unittest.main()
