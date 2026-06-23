"""news 包(v1.6 S5):provider 解析 / key 解析 / 选源 / 去重 / RSS 解析(全离线)。"""

import unittest
from unittest import mock

from newsletter.news import registry
from newsletter.news.base import NewsItem
from newsletter.news.rss import parse_feed
from newsletter.news.thenewsapi import TheNewsApiProvider, _keys_from_env


class TestTheNewsApiParse(unittest.TestCase):
    def test_to_items(self):
        data = [
            {"uuid": "u1", "title": "Gold rises", "url": "https://x.com/a", "source": "cnbc.com",
             "published_at": "2026-06-14T08:30:00.000000Z", "description": "desc", "snippet": "snip"},
            {"uuid": "u2", "title": "No url dropped", "source": "y.com"},  # 无 url → 丢
        ]
        items = TheNewsApiProvider._to_items(data, asset="XAUUSD")
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it.uuid, it.source, it.link, it.asset), ("u1", "cnbc.com", "https://x.com/a", "XAUUSD"))
        self.assertEqual(it.published, "2026-06-14T08:30:00")  # 截到秒
        self.assertEqual(it.summary, "desc")  # 优先 description


class TestKeysFromEnv(unittest.TestCase):
    def test_multi_keys_priority(self):
        with mock.patch.dict("os.environ", {"THENEWSAPI_KEYS": "a, b ,c", "THENEWSAPI_KEY": "z"}, clear=False):
            self.assertEqual(_keys_from_env(), ["a", "b", "c"])

    def test_single_key_fallback(self):
        env = {"THENEWSAPI_KEY": "solo"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(_keys_from_env(), ["solo"])

    def test_no_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_keys_from_env(), [])

    def test_key_rotation(self):
        p = TheNewsApiProvider(keys=["k1", "k2", "k3"])
        self.assertEqual([p._next_key() for _ in range(4)], ["k1", "k2", "k3", "k1"])


class TestProviderSelection(unittest.TestCase):
    def test_none_mode_empty(self):
        self.assertEqual(registry.build_providers("none"), [])

    def test_live_without_keys_only_rss(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            ps = registry.build_providers("live")
        self.assertEqual([p.name for p in ps], ["rss"])

    def test_live_with_keys_has_both(self):
        with mock.patch.dict("os.environ", {"THENEWSAPI_KEYS": "k1"}, clear=True):
            ps = registry.build_providers("live")
        self.assertEqual({p.name for p in ps}, {"thenewsapi", "rss"})

    def test_backfill_no_rss(self):
        with mock.patch.dict("os.environ", {"THENEWSAPI_KEYS": "k1"}, clear=True):
            ps = registry.build_providers("backfill")
        self.assertEqual([p.name for p in ps], ["thenewsapi"])


class TestDedup(unittest.TestCase):
    def test_dedup_by_uuid_then_title(self):
        items = [
            NewsItem(source="a", title="T1", link="u", uuid="x"),
            NewsItem(source="b", title="T1-dup", link="u2", uuid="x"),  # 同 uuid → 丢
            NewsItem(source="c", title="Same Title", link="u3"),
            NewsItem(source="d", title="same title", link="u4"),  # 同标题(大小写)→ 丢
        ]
        out = registry._dedup(items)
        self.assertEqual([i.uuid or i.title for i in out], ["x", "Same Title"])


class TestRssParse(unittest.TestCase):
    def test_rss_item(self):
        xml = b"""<rss><channel>
          <item><title>Fed holds rates</title><link>https://f.org/1</link>
            <pubDate>Mon, 01 Jun 2026</pubDate><description>&lt;p&gt;body&lt;/p&gt;</description></item>
        </channel></rss>"""
        items = parse_feed("Fed", xml)
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0].title, items[0].link, items[0].source), ("Fed holds rates", "https://f.org/1", "Fed"))
        self.assertEqual(items[0].summary, "body")  # HTML 去标签

    def test_atom_entry(self):
        xml = b"""<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>ECB note</title><link rel="alternate" href="https://ecb.eu/x"/>
            <updated>2026-06-02</updated><summary>hello</summary></entry>
        </feed>"""
        items = parse_feed("ECB", xml)
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0].title, items[0].link), ("ECB note", "https://ecb.eu/x"))


if __name__ == "__main__":
    unittest.main()
