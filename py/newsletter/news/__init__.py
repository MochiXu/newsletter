"""新闻多接口包(v1.6 S5)。

公共 API(向后兼容旧 `news.py`):`NewsItem` / `fetch_news` / `classify`。
源:`rss`(免 key 兜底)+ `thenewsapi`(主源,多 key + 浏览器 UA + 源白名单)。多源可插拔(`base.NewsProvider`)。
"""

from __future__ import annotations

from .base import NewsItem, NewsProvider
from .classify import NEWS_SCHEMA, NEWS_SYSTEM, classify
from .extract import enrich  # 注:不导出函数 extract,避免遮蔽子模块 news.extract
from .features import build_article_records, compute_news_features, compute_news_trends
from .registry import MACRO_QUERIES, ROSTER_QUERIES, build_providers, fetch_news
from .rss import DEFAULT_FEEDS, RssProvider, fetch_feed, parse_feed
from .store import NewsStore
from .thenewsapi import SOURCE_ALLOWLIST, TheNewsApiProvider

__all__ = [
    "NewsItem", "NewsProvider", "fetch_news", "classify", "NEWS_SCHEMA", "NEWS_SYSTEM",
    "build_providers", "ROSTER_QUERIES", "MACRO_QUERIES", "RssProvider", "TheNewsApiProvider",
    "SOURCE_ALLOWLIST", "DEFAULT_FEEDS", "parse_feed", "fetch_feed",
    "enrich", "compute_news_features", "build_article_records", "compute_news_trends", "NewsStore",
]
