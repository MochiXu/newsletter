"""新闻 → 代码特征(v1.6 S5c)。

把分类后的新闻聚合成**代码算的、可喂 LLM 的受治理特征**(不是裸情绪散文,避免信心通胀):
- 每资产:新闻量 count + 净情绪 netSentiment(分类 direction:up=+1/down=-1/watch=0 的均值)。
- 全局事件标记:今日新闻是否提及 FOMC / CPI / 就业 / 地缘(关键词扫描)——催化剂感知,助校准。

诚实边界(见 docs/refactor/v1.6-progress.md §6):新闻方向预测力弱;这些只作 B 臂的代码特征,由 A/B 裁决价值。
- **新闻量 z**(对历史均值)需累积每日计数,本期先给 raw count;**惊喜=actual−consensus** 需外部预期数据,留后续。
"""

from __future__ import annotations

import re

from .base import NewsItem

# 分类的中文资产名 → roster series_id(RSS/通用新闻无 asset 归属时,靠分类 affected_assets 回填)。
_ASSET_ALIAS: dict[str, str] = {
    "美股": "NASDAQCOM", "纳指": "NASDAQCOM", "股市": "NASDAQCOM", "股指": "NASDAQCOM",
    "黄金": "XAUUSD", "金价": "XAUUSD",
    "美元": "DTWEXBGS", "汇率": "DTWEXBGS",
    "美债": "DGS2", "国债": "DGS2", "利率": "DGS2", "收益率": "DGS2",
}
_ROSTER = ("NASDAQCOM", "XAUUSD", "DTWEXBGS", "DGS2")
_DIR_SIGN = {"up": 1, "down": -1, "watch": 0}

# 事件关键词(标题/正文为英文)。值=正则。
_EVENT_PATTERNS: dict[str, re.Pattern] = {
    "fomc": re.compile(r"\bfomc\b|federal reserve|fed (meeting|decision|rate|chair)|powell|rate decision|dot plot", re.I),
    "cpi": re.compile(r"\bcpi\b|inflation (data|report|print)|consumer price", re.I),
    "jobs": re.compile(r"nonfarm|non-farm|payroll|jobs report|unemployment|jobless", re.I),
    "geo": re.compile(r"\bwar\b|sanction|tariff|geopolit|conflict|\bopec\b", re.I),
}


def _alias_assets(affected) -> set[str]:
    out: set[str] = set()
    for a in affected or []:
        for name, sid in _ASSET_ALIAS.items():
            if name in str(a):
                out.add(sid)
    return out


def _assets_of(it: NewsItem, c: dict | None) -> set[str]:
    """该条新闻关乎哪些 roster 资产:优先 API 查询归属 it.asset,否则分类 affected_assets 映射。"""
    if it.asset in _ROSTER:
        return {it.asset}
    return _alias_assets((c or {}).get("affected_assets"))


def compute_news_features(items: list[NewsItem], classified: list[dict] | None) -> dict:
    """聚合成 {byAsset:{sid:{count,netSentiment,headlines}}, events:{...bool}, total}。

    classified 按 `index`(从 1)对齐 items(同 _merge_news);category=噪音 的不计入。
    """
    by_idx: dict[int, dict] = {}
    for c in classified or []:
        try:
            by_idx[int(c.get("index"))] = c
        except (TypeError, ValueError):
            pass

    agg: dict[str, dict] = {sid: {"signs": [], "headlines": []} for sid in _ROSTER}
    events = {k: False for k in _EVENT_PATTERNS}
    corpus_parts: list[str] = []
    total = 0

    for i, it in enumerate(items):
        c = by_idx.get(i + 1)
        if c and c.get("category") == "噪音":
            continue
        total += 1
        corpus_parts.append(f"{it.title} {it.text or it.summary}")
        sign = _DIR_SIGN.get((c or {}).get("direction", "watch"), 0)
        for sid in _assets_of(it, c):
            agg[sid]["signs"].append(sign)
            if len(agg[sid]["headlines"]) < 3:
                agg[sid]["headlines"].append(it.title)

    corpus = " ".join(corpus_parts)
    for name, pat in _EVENT_PATTERNS.items():
        events[name] = bool(pat.search(corpus))

    by_asset: dict[str, dict] = {}
    for sid in _ROSTER:
        signs = agg[sid]["signs"]
        if not signs:
            continue
        by_asset[sid] = {
            "count": len(signs),
            "netSentiment": round(sum(signs) / len(signs), 3),
            "headlines": agg[sid]["headlines"],
        }
    return {"byAsset": by_asset, "events": events, "total": total}
