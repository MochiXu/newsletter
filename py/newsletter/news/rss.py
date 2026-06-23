"""RSS/Atom 新闻源(stdlib;免 key、无历史、feed-based)。

迁自旧 `news.py`。作为 live 兜底源 + 央行一手消息(Fed/ECB)。不支持按 query/日期查询。
"""

from __future__ import annotations

import re
import urllib.request
from xml.etree import ElementTree as ET

from .base import NewsItem

# 默认 RSS 源(免鉴权,偏宏观/市场;权威央行在前)。失效源静默跳过。
DEFAULT_FEEDS = [
    ("Fed", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("ECB", "https://www.ecb.europa.eu/rss/press.xml"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
]


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _first(parent, name: str):
    for e in parent.iter():
        if _local(e.tag) == name:
            return e
    return None


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:300]


def _atom_link(entry) -> str:
    links = [e for e in list(entry) if _local(e.tag) == "link"]
    for e in links:
        if e.get("rel") in (None, "", "alternate") and e.get("href"):
            return e.get("href")
    for e in links:
        if e.get("href"):
            return e.get("href")
    return ""


def parse_feed(source: str, xml_bytes: bytes) -> list[NewsItem]:
    """解析 RSS(channel/item)或 Atom(entry)。无法解析返回 []。"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    items: list[NewsItem] = []
    rss_items = [e for e in root.iter() if _local(e.tag) == "item"]
    if rss_items:
        for it in rss_items:
            title = _text(_first(it, "title"))
            if not title:
                continue
            pub = _text(_first(it, "pubDate")) or _text(_first(it, "date"))
            items.append(
                NewsItem(
                    source=source,
                    title=title,
                    link=_text(_first(it, "link")),
                    published=pub,
                    summary=_strip_html(_text(_first(it, "description"))),
                )
            )
        return items

    for en in [e for e in root.iter() if _local(e.tag) == "entry"]:
        title = _text(_first(en, "title"))
        if not title:
            continue
        link = _atom_link(en) or _text(_first(en, "link"))
        pub = _text(_first(en, "updated")) or _text(_first(en, "published"))
        summ = _text(_first(en, "summary")) or _text(_first(en, "content"))
        items.append(NewsItem(source=source, title=title, link=link, published=pub, summary=_strip_html(summ)))
    return items


def fetch_feed(source: str, url: str, timeout: int = 15) -> list[NewsItem]:
    req = urllib.request.Request(url, headers={"User-Agent": "newsletter-m2/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_feed(source, resp.read())


class RssProvider:
    """RSS 源(feed-based:忽略 query/日期,返回各 feed 最新条目)。"""

    name = "rss"
    needs_key = False
    supports_query = False

    def __init__(self, feeds=None, per_feed: int = 3):
        self.feeds = feeds or DEFAULT_FEEDS
        self.per_feed = per_feed

    def fetch(self, query=None, start=None, end=None, limit: int = 25) -> list[NewsItem]:
        collected: list[NewsItem] = []
        for source, url in self.feeds:
            try:
                collected.extend(fetch_feed(source, url)[: self.per_feed])
            except Exception:  # noqa: BLE001 — 单源失败静默跳过
                continue
        return collected[:limit]
