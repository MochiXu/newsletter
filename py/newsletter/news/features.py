"""新闻 → 代码特征(v1.8 P3/P4/P5)。

三类产出(都"代码算特征、LLM 只标注"):
1. `build_article_records`:逐篇 → 入库记录(LLM 标签 + 代码文本信号),写 `NewsStore`。
2. `compute_news_features`:**当天截面**聚合(量/连续净情绪/分歧度/事件/EPU/GPR/鹰鸽/类别构成)→ 喂 B 臂。
3. `compute_news_trends`:从语料库历史算**滚动时序**(情绪走势/动量/异常量 z)→ 喂 B 臂(P5)。

诚实边界(见 v1.8 §0):新闻方向力弱(反身性)→ 主用于事件感知/校准 + 背离;只前向可信;走 A/B 裁决。
"""

from __future__ import annotations

import pandas as pd

from .. import tsfeatures as ts
from . import textsignals as txt
from .base import NewsItem

# 分类的中文资产名 → roster series_id(RSS/通用新闻无 asset 归属时,靠分类 affected_assets 回填)。
_ASSET_ALIAS: dict[str, str] = {
    "美股": "NASDAQCOM", "纳指": "NASDAQCOM", "股市": "NASDAQCOM", "股指": "NASDAQCOM",
    "黄金": "XAUUSD", "金价": "XAUUSD",
    "美元": "DTWEXBGS", "汇率": "DTWEXBGS",
    "美债": "DGS2", "国债": "DGS2", "利率": "DGS2", "收益率": "DGS2",
}
_ROSTER = ("NASDAQCOM", "XAUUSD", "DTWEXBGS", "DGS2")
_DIR_SIGN = {"up": 1.0, "down": -1.0, "watch": 0.0}


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


def _sentiment_of(c: dict | None) -> float:
    """连续情绪 ∈ [-1,1]:优先 LLM 的 sentiment,退回 direction 符号。"""
    if c:
        v = c.get("sentiment")
        if isinstance(v, (int, float)):
            return max(-1.0, min(1.0, float(v)))
        return _DIR_SIGN.get(c.get("direction", "watch"), 0.0)
    return 0.0


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _text_of(it: NewsItem) -> str:
    return f"{it.title} {it.text or it.summary or ''}"


# ── 1) 逐篇入库记录(LLM 标签 + 代码文本信号)──────────────────────────────
def build_article_records(items: list[NewsItem], classified: list[dict] | None,
                          source_tag: str = "forward") -> list[dict]:
    """逐篇 → NewsStore 入库 dict(含代码算的 EPU/GPR/鹰鸽/事件)。噪音也入库(category=噪音,聚合时再排除)。"""
    by_idx: dict[int, dict] = {}
    for c in classified or []:
        try:
            by_idx[int(c.get("index"))] = c
        except (TypeError, ValueError):
            pass
    out: list[dict] = []
    for i, it in enumerate(items):
        c = by_idx.get(i + 1)
        body = it.text or ""
        text = _text_of(it)
        out.append({
            "uuid": it.uuid or it.link, "published_at": it.published, "source": it.source,
            "domain": it.source, "url": it.link, "title": it.title, "description": it.summary,
            "body": body, "word_count": txt.word_count(text),
            "category": (c or {}).get("category", ""), "direction": (c or {}).get("direction", ""),
            "sentiment_score": _sentiment_of(c) if c else float("nan"),
            "affected_assets": sorted(_assets_of(it, c)), "summary": (c or {}).get("summary", ""),
            "event_types": txt.event_types(text),
            "uncertainty_score": txt.uncertainty_density(text), "hawkish_dovish": txt.hawkish_dovish(text),
            "extra": {"epu": txt.epu_score(text), "gpr": txt.gpr_density(text)},
            "source_tag": source_tag,
        })
    return out


# ── 2) 当天截面聚合 ────────────────────────────────────────────────────────
def compute_news_features(items: list[NewsItem], classified: list[dict] | None) -> dict:
    """当天截面特征:每资产量/连续净情绪/分歧度/方向票 + 全局事件/EPU/GPR/不确定/鹰鸽/类别构成。"""
    by_idx: dict[int, dict] = {}
    for c in classified or []:
        try:
            by_idx[int(c.get("index"))] = c
        except (TypeError, ValueError):
            pass

    per_asset: dict[str, dict] = {sid: {"sent": [], "votes": {"up": 0, "down": 0, "watch": 0}, "headlines": []} for sid in _ROSTER}
    events = {k: False for k in txt.EVENT_PATTERNS}
    epu, gpr, unc, hd, cat_mix = [], [], [], [], {}
    total = 0

    for i, it in enumerate(items):
        c = by_idx.get(i + 1)
        if c and c.get("category") == "噪音":
            continue
        total += 1
        text = _text_of(it)
        epu.append(txt.epu_score(text))
        gpr.append(txt.gpr_density(text))
        unc.append(txt.uncertainty_density(text))
        if (v := txt.hawkish_dovish(text)) is not None:
            hd.append(v)
        for ev in txt.event_types(text):
            events[ev] = True
        cat = (c or {}).get("category") or "未分类"
        cat_mix[cat] = cat_mix.get(cat, 0) + 1
        sent = _sentiment_of(c)
        direction = (c or {}).get("direction", "watch")
        for sid in _assets_of(it, c):
            per_asset[sid]["sent"].append(sent)
            per_asset[sid]["votes"][direction] = per_asset[sid]["votes"].get(direction, 0) + 1
            if len(per_asset[sid]["headlines"]) < 3:
                per_asset[sid]["headlines"].append(it.title)

    by_asset: dict[str, dict] = {}
    for sid in _ROSTER:
        sents = per_asset[sid]["sent"]
        if not sents:
            continue
        by_asset[sid] = {
            "count": len(sents),
            "netSentiment": _mean(sents),
            "sentimentDispersion": ts.dispersion(sents),  # 新闻在打架=不确定性↑(利校准)
            "directionVotes": per_asset[sid]["votes"],
            "headlines": per_asset[sid]["headlines"],
        }
    return {
        "byAsset": by_asset, "events": events, "total": total,
        "epu": _mean(epu), "gpr": _mean(gpr), "uncertainty": _mean(unc), "hawkishDovish": _mean(hd),
        "categoryMix": cat_mix,
    }


# ── 3) 滚动时序(从语料库历史)─────────────────────────────────────────────
def compute_news_trends(store_df: pd.DataFrame, target_date: str,
                        windows: tuple[int, ...] = (5, 20, 60),
                        price_returns: dict[str, float] | None = None) -> dict:
    """从语料库 article-level 帧算每资产的**滚动情绪走势 + 动量 + 异常量 z + 情绪—价格背离**(截至 target_date,因果)。

    store_df 需含 published_at / affected_assets(JSON 串)/ sentiment_score。空 → {}。
    price_returns:{sid: 同窗口价格收益},给则算 `divergence`(情绪 − 价格,正=情绪比价格乐观=背离观察点)。
    """
    import math

    if store_df is None or store_df.empty:
        return {}
    df = store_df.copy()
    df["day"] = df["published_at"].astype(str).str[:10]
    df = df[df["day"] <= target_date]
    if df.empty:
        return {}
    import json

    out: dict[str, dict] = {}
    for sid in _ROSTER:
        # 该资产相关文章(affected_assets JSON 串含 sid)
        mask = df["affected_assets"].astype(str).apply(lambda s: sid in (json.loads(s) if s.startswith("[") else []))
        sub = df[mask]
        if sub.empty:
            continue
        daily = sub.groupby("day").agg(sent=("sentiment_score", "mean"), vol=("uuid", "count")).sort_index()
        sent = daily["sent"].astype(float)
        vol = daily["vol"].astype(float)
        feat: dict[str, float] = {}
        for w in windows:
            m = ts.rolling_mean(sent, w)
            feat[f"sentMean{w}"] = round(float(m.iloc[-1]), 4) if m.notna().any() else None
        slp = ts.slope(sent, min(10, len(sent)))  # 情绪斜率(在走强/走弱;短序列稳健)
        feat["sentMomentum"] = round(float(slp.dropna().iloc[-1]), 4) if slp.notna().any() else None
        zv = ts.zscore(vol, 20)  # 新闻量异常 z(关注飙升,需 ~10+ 天历史)
        feat["volumeZ"] = round(float(zv.dropna().iloc[-1]), 4) if zv.notna().any() else None
        st = ts.streak(ts.momentum(ts.rolling_mean(sent, 5), 1))  # 情绪连续走强/走弱天数
        feat["sentStreak"] = float(st.dropna().iloc[-1]) if st.notna().any() else None
        # 情绪—价格背离(P4):情绪[-1,1] vs 价格收益(tanh 压到同量级)。正=情绪比价格乐观 → 背离观察点
        pr = (price_returns or {}).get(sid)
        if pr is not None and feat.get("sentMean20") is not None:
            feat["priceRet20"] = round(float(pr), 4)
            feat["divergence"] = round(feat["sentMean20"] - math.tanh(float(pr) * 20.0), 4)
        out[sid] = feat
    return out
