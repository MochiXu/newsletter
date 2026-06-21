"""新闻抓取 + 分类(事实 / 解读 / 影响资产)—— M2。

- 抓取:stdlib `urllib` + `xml.etree` 解析 RSS/Atom(无第三方依赖)。
- 分类:复用 providers 的 LLM provider(`call_structured`);无 provider → 返回 None(不分类)。

这是用户最初提的核心功能之一:把新闻按「事实 / 解释 / 影响资产」分类。
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .llm.providers import select_provider

# 默认 RSS 源(免鉴权,偏宏观/市场)。可由调用方覆盖;失效的源会被静默跳过。
# 顺序 = 优先级(权威央行在前,受 total 截断时优先保留);均已实测能拉到带链接的条目。
DEFAULT_FEEDS = [
    ("Fed", "https://www.federalreserve.gov/feeds/press_all.xml"),  # 美联储新闻
    ("ECB", "https://www.ecb.europa.eu/rss/press.xml"),  # 欧洲央行新闻
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),  # 市场/经济快讯
    ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),  # CNBC 经济(非泛新闻)
]


@dataclass
class NewsItem:
    source: str
    title: str
    link: str
    published: str
    summary: str


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
    """Atom entry 常有多个 <link>;优先 rel=alternate(或无 rel)的文章链接,而非 self/edit。"""
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

    # Atom
    for en in [e for e in root.iter() if _local(e.tag) == "entry"]:
        title = _text(_first(en, "title"))
        if not title:
            continue
        link = _atom_link(en) or _text(_first(en, "link"))
        pub = _text(_first(en, "updated")) or _text(_first(en, "published"))
        summ = _text(_first(en, "summary")) or _text(_first(en, "content"))
        items.append(NewsItem(source, title, link, pub, _strip_html(summ)))
    return items


def fetch_feed(source: str, url: str, timeout: int = 15) -> list[NewsItem]:
    req = urllib.request.Request(url, headers={"User-Agent": "newsletter-m2/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_feed(source, resp.read())


def fetch_news(feeds=None, per_feed: int = 3, total: int = 12) -> list[NewsItem]:
    """抓取并汇总多个源;单源失败静默跳过;按标题去重后截断到 total 条。

    per_feed 默认 3:让多个源均衡进入(避免靠前的源把 total 名额占满,挤掉后面的源)。
    """
    feeds = feeds or DEFAULT_FEEDS
    collected: list[NewsItem] = []
    for source, url in feeds:
        try:
            collected.extend(fetch_feed(source, url)[:per_feed])
        except Exception:
            continue
    seen: set[str] = set()
    uniq: list[NewsItem] = []
    for it in collected:
        key = it.title.strip().lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append(it)
    return uniq[:total]


# ── 分类 ──────────────────────────────────────────────────────────────

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "对应输入列表的编号(从 1 开始),用于对齐——务必填准",
                    },
                    "title": {"type": "string", "description": "原标题(保持英文原文,不要翻译)"},
                    "category": {
                        "type": "string",
                        "enum": ["事实", "解读", "事实+解读", "噪音"],
                        "description": "这条新闻主要是客观事实、主观解读、二者皆有,还是无信息量的噪音",
                    },
                    "summary": {"type": "string", "description": "中文一句话概括"},
                    "affected_assets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "主要受影响资产(如 美债/黄金/美元/美股/A股/比特币)",
                    },
                    "note": {"type": "string", "description": "对资产的方向性影响,简短;非买卖建议"},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "watch"],
                        "description": "该新闻对主要受影响资产的方向性:up=利多/上行,down=利空/下行,watch=方向待观察",
                    },
                },
                "required": ["index", "title", "category", "summary", "affected_assets", "direction"],
            },
        }
    },
    "required": ["items"],
}

NEWS_SYSTEM = (
    "你是宏观新闻分类助手。把每条新闻分为『事实/解读/事实+解读/噪音』,"
    "用中文一句话概括,列出主要受影响资产,简述方向性影响,并给出方向 direction(up/down/watch)。"
    "严格区分客观事实与主观解读;绝不给买/卖建议,不承诺收益。"
)


def classify(items: list[NewsItem]) -> list[dict] | None:
    """逐条分类;无 LLM provider 或无新闻时返回 None。返回与 items 等长的分类列表。"""
    provider = select_provider()
    if provider is None or not items:
        return None
    listing = "\n".join(
        f"{i + 1}. [{it.source}] {it.title}" + (f" — {it.summary}" if it.summary else "")
        for i, it in enumerate(items)
    )
    user = (
        "请对以下每条新闻分类。每条返回的 index 必须等于该条前面的编号(从 1 开始),"
        "title 保持英文原文不要翻译,category/summary/note 用中文,direction 用 up/down/watch:\n" + listing
    )
    result = provider.call_structured(
        NEWS_SYSTEM, user, "classify_news", "对新闻逐条分类(事实/解读/影响资产)", NEWS_SCHEMA
    )
    return result.get("items")
