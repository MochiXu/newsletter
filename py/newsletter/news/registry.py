"""新闻多源编排(v1.6 S5):按 news_mode 选源 → 每资产查询 → 跨源合并去重。

多源可插拔(`NewsProvider`)。本期实例化 RSS + TheNewsAPI;缺 key 的源自动跳过,RSS 永远在。
新闻是多源**并集**(非"首个成功"),按 uuid/标题去重。
"""

from __future__ import annotations

import logging

from .. import catalog
from .base import NewsItem
from .rss import RssProvider
from .thenewsapi import TheNewsApiProvider

log = logging.getLogger(__name__)

# 每个 roster 资产的检索关键词(TheNewsAPI search 语法:| =OR,"..."=短语)。v1.8 扩充。
ROSTER_QUERIES: dict[str, str] = {
    "NASDAQCOM": 'nasdaq | "stock market" | equities | "wall street" | "tech stocks" | "S&P 500" | semiconductor',
    "XAUUSD": 'gold | bullion | "gold price" | "safe haven" | "real yields" | "central bank gold"',
    "DTWEXBGS": '"us dollar" | "dollar index" | forex | greenback | "dollar strength" | "currency markets"',
    "DGS2": '"treasury yield" | "federal reserve" | "interest rate" | "fed rate" | FOMC | Powell | "rate cut" | "rate hike" | "dot plot"',
}

# 跨资产宏观主题频道(v1.8 §7):影响全体的事件/政策新闻 → 喂事件标记 + EPU/GPR/鹰鸽 + 各资产分类回填。
# asset="" → 靠分类的 affected_assets 归属;同时贡献全局信号(政策不确定/地缘/央行语调)。
MACRO_QUERIES: tuple[str, ...] = (
    'federal reserve | FOMC | Powell | "monetary policy" | "rate decision"',
    '"treasury secretary" | "fiscal policy" | tariff | Trump | "debt ceiling"',
    'geopolitical | war | sanctions | OPEC | "oil price" | "energy crisis"',
    '"european central bank" | ECB | "bank of japan" | "global economy"',
)


def build_providers(news_mode: str):
    """按 news_mode 选源。live=RSS+TheNewsAPI;backfill=TheNewsAPI;none=[]。缺 key 的源跳过。"""
    if news_mode == "none":
        return []
    providers = []
    tna = TheNewsApiProvider()
    if tna.keys:  # 有 key 才用
        providers.append(tna)
    else:
        log.info("THENEWSAPI_KEYS 未配置,跳过 TheNewsAPI 源")
    if news_mode == "live":
        providers.append(RssProvider())  # 央行一手 + 兜底(无配额)
    return providers


def _dedup(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    out: list[NewsItem] = []
    for it in items:
        key = (it.uuid or it.title or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def fetch_news(
    news_mode: str = "live",
    start: str | None = None,
    end: str | None = None,
    per_asset: int = 15,  # Basic 档:每资产抓 ~15 条优质(免费档曾是 3);v1.8
    macro: bool = True,  # 是否额外抓跨资产宏观主题频道(v1.8 §7)
) -> list[NewsItem]:
    """拉新闻并去重。query 源:roster 各资产 + 宏观主题频道分别查询;feed 源(RSS)整抓。"""
    providers = build_providers(news_mode)
    collected: list[NewsItem] = []
    for p in providers:
        if getattr(p, "supports_query", False):
            for sid in catalog.PREDICTION_TARGET_IDS:
                try:
                    collected.extend(
                        p.fetch(query=ROSTER_QUERIES.get(sid), start=start, end=end, limit=per_asset, asset=sid)
                    )
                except Exception as e:  # noqa: BLE001 — 单查询失败不阻断
                    log.warning("news provider %s asset %s failed: %s", getattr(p, "name", "?"), sid, e)
            if macro:  # 宏观主题频道(asset="" → 靠分类回填资产 + 贡献全局事件/EPU/GPR)
                for q in MACRO_QUERIES:
                    try:
                        collected.extend(p.fetch(query=q, start=start, end=end, limit=per_asset, asset=""))
                    except Exception as e:  # noqa: BLE001
                        log.warning("news provider %s macro query failed: %s", getattr(p, "name", "?"), e)
        else:
            try:
                collected.extend(p.fetch(limit=per_asset * 4))
            except Exception as e:  # noqa: BLE001
                log.warning("news provider %s failed: %s", getattr(p, "name", "?"), e)
    return _dedup(collected)
