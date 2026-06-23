"""news.extract / cache(v1.6 S5b):正文抽取 / 死链丢弃 / 缓存(全离线,monkeypatch 网络)。"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from newsletter.news import extract as ex
from newsletter.news.base import NewsItem
from newsletter.news.cache import ExtractCache, _safe_key

_LONG = "Gold prices rose as the Federal Reserve signaled a pause. " * 8  # >120 字真实文本
_HTML = f"<html><head><style>x{{}}</style></head><body><nav>menu</nav><p>{_LONG}</p>" \
        "<script>var a=1;</script></body></html>"


class TestHeuristic(unittest.TestCase):
    def test_strips_script_style_tags(self):
        out = ex._heuristic(_HTML)
        self.assertIn("Gold prices rose", out)
        self.assertNotIn("var a=1", out)  # script 去掉
        self.assertNotIn("<", out)        # 标签去掉


class TestExtract(unittest.TestCase):
    def test_extract_ok(self):
        with mock.patch.object(ex, "_fetch_html", return_value=_HTML):
            text = ex.extract("https://x.com/a")
        self.assertIsNotNone(text)
        self.assertIn("Gold prices rose", text)
        self.assertLessEqual(len(text), ex._MAX_CHARS)

    def test_dead_link_none(self):
        with mock.patch.object(ex, "_fetch_html", return_value=None):
            self.assertIsNone(ex.extract("https://dead.example/x"))

    def test_too_short_none(self):
        with mock.patch.object(ex, "_fetch_html", return_value="<p>tiny</p>"):
            self.assertIsNone(ex.extract("https://x.com/short"))

    def test_empty_url(self):
        self.assertIsNone(ex.extract(""))


class TestEnrich(unittest.TestCase):
    def _items(self):
        return [NewsItem(source="a", title="T1", link="u1", uuid="x1"),
                NewsItem(source="b", title="T2", link="u2", uuid="x2")]

    def test_drop_on_fail(self):
        # u1 抽到正文、u2 死链 → 默认丢弃 u2
        def fake(url): return "some long body text " * 10 if url == "u1" else None
        with mock.patch.object(ex, "extract", side_effect=fake):
            out = ex.enrich(self._items())
        self.assertEqual([i.uuid for i in out], ["x1"])
        self.assertTrue(out[0].text)

    def test_keep_on_fail(self):
        with mock.patch.object(ex, "extract", return_value=None):
            out = ex.enrich(self._items(), drop_on_fail=False)
        self.assertEqual(len(out), 2)  # 不丢
        self.assertEqual(out[0].text, "")

    def test_cache_hit_skips_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            cache = ExtractCache(Path(d))
            cache.put("x1", "cached body text that is long enough to keep around")
            with mock.patch.object(ex, "extract", side_effect=AssertionError("should not fetch")) as m:
                out = ex.enrich([NewsItem(source="a", title="T1", link="u1", uuid="x1")], cache=cache)
            self.assertEqual(out[0].text, "cached body text that is long enough to keep around")
            m.assert_not_called()


class TestCache(unittest.TestCase):
    def test_round_trip_and_safe_key(self):
        with tempfile.TemporaryDirectory() as d:
            c = ExtractCache(Path(d))
            self.assertIsNone(c.get("nope"))
            c.put("uuid-123", "hello")
            self.assertEqual(c.get("uuid-123"), "hello")
            # url 这类不安全 key → 哈希成文件名(不抛)
            url = "https://x.com/a?b=1&c=2"
            c.put(url, "body")
            self.assertEqual(c.get(url), "body")
            self.assertNotIn("/", _safe_key(url))


if __name__ == "__main__":
    unittest.main()
