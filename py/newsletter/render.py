"""渲染层:LLM 输出 + 数据/特征 → 前端 Brief 契约(JSON)+ markdown + 飞书文本。

LLM 原始输出已在 `llm.service` 经 `LLMBrief` 校验/归一化(facts 不再泄漏 dict)。本层把它和
指标表/复盘/新闻组装成 `models.Brief`(严格对齐 types.ts),并维护聚合 `briefs.json`。
"""

from __future__ import annotations

import datetime
import json
from typing import Any

import pandas as pd

from . import catalog, features
from .config import Paths
from .textnorm import normalize_text
from .models import (
    Brief,
    BriefsPayload,
    ConsensusItem,
    Dir,
    Hypothesis,
    Impact,
    LLMBrief,
    Metric,
    ModelView,
    News,
    NewsCat,
    OFFLINE_MODEL_ID,
    PricePoint,
    Review,
    ReviewStatus,
    Signal,
    Tone,
)

DISCLAIMER = "_本简报由 AI 自动生成,仅为研究框架与观察点,不构成投资建议,不承诺收益。_"
_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
# 后端中文新闻分类 → 前端英文枚举
_CAT_EN = {"事实": "fact", "解读": "read", "事实+解读": "both", "噪音": "noise"}


def weekday_cn(date_str: str) -> str:
    try:
        y, m, d = (int(x) for x in date_str.split("-"))
        return _WEEKDAYS[datetime.date(y, m, d).weekday()]
    except (ValueError, TypeError):
        return ""


# ── 契约组装 ────────────────────────────────────────────────────────────
def build_metrics(long_df: pd.DataFrame, target_date: str) -> list[Metric]:
    """据展示指标集 + 真实观测点的电平/日变化,构造前端指标表。"""
    out: list[Metric] = []
    for spec in catalog.DISPLAY_METRICS:
        lc = features.metric_level_change(long_df, spec.series_id, target_date)
        if lc is None:
            continue  # 某序列缺失则跳过,表格行数自适应
        level, change = lc
        out.append(
            Metric(
                key=spec.series_id.lower(),
                label=spec.metric_label,
                value=round(level, 4),
                change=round(change, 4),
                kind=spec.metric_kind,  # type: ignore[arg-type]
                spark=features.metric_spark(long_df, spec.series_id, target_date),
            )
        )
    return out


def build_price_series(long_df: pd.DataFrame, target_date: str) -> dict[str, list[PricePoint]]:
    """按 chart roster 构造 30 日价格序列(key=series_id 小写,与 metrics.key 对齐;缺失跳过)。"""
    out: dict[str, list[PricePoint]] = {}
    for sid in catalog.CHART_SERIES_IDS:
        pts = features.price_series(long_df, sid, target_date)
        if pts:
            out[sid.lower()] = [PricePoint(date=str(p["date"]), value=float(p["value"])) for p in pts]
    return out


def build_signals(snap: dict[str, float]) -> list[Signal]:
    """据特征视图注册表,把特征快照(snap)序列化成前端 signals 列表(缺失项自动跳过)。"""
    out: list[Signal] = []
    for key, label, unit, group in features.FEATURE_VIEW:
        if key in snap:
            out.append(Signal(key=key, label=label, value=round(float(snap[key]), 6), unit=unit, group=group))
    return out


def build_news(merged: list[dict[str, Any]]) -> list[News]:
    """组装前端新闻列表。展示层过滤:丢弃「噪音」类与无链接项(点不开的不展示)。"""
    out: list[News] = []
    for n in merged or []:
        cat_cn = n.get("category")
        cat = NewsCat(_CAT_EN[cat_cn]) if cat_cn in _CAT_EN else None
        if cat == NewsCat.NOISE:
            continue  # 噪音不展示
        if not (n.get("link") or "").strip():
            continue  # 无源链接(前端点不开)不展示
        out.append(
            News(
                title=n.get("title", ""),
                source=n.get("source", ""),
                cat=cat,
                assets=list(n.get("affected_assets") or []),
                dir=Dir(n["direction"]) if n.get("direction") in ("up", "down", "watch") else Dir.WATCH,
                link=n.get("link", "") or "",
            )
        )
    return out


# figure token 后可并入的单位(长优先,使 '7.8' 在 '7.8%' 时整段一起上色;'15' 在 '15bps' 时取 bps)
_FIG_UNITS = ("bps", "bp", "%", "‰")


def _expand_fig_token(text: str, tok: str) -> str:
    """token 后在 text 中若紧跟单位(%/bp/bps/‰),把单位并入,使整段一起上色;否则原样。"""
    if any(tok.endswith(u) for u in _FIG_UNITS):
        return tok  # 已带单位
    start = 0
    while (idx := text.find(tok, start)) >= 0:
        after = text[idx + len(tok):]
        for u in _FIG_UNITS:
            if after.startswith(u):
                return tok + u
        start = idx + 1
    return tok


def _resolve_fig_token(text: str, tok: str) -> str | None:
    """把 LLM 的 figure token 落实成 text 里可匹配的子串:
    优先原样;原样不在正文时退化为去掉前导 +/-(LLM 常给 token 带符号,正文却用「升/跌」表方向)再找;
    命中即并入紧邻单位。连去符号也找不到 = 死 figure → None(上层丢弃,免得前端静默匹配不到)。"""
    cands = [tok, tok[1:]] if tok[:1] in "+-" else [tok]
    for cand in cands:
        if cand and cand in text:
            return _expand_fig_token(text, cand)
    return None


def _norm_tagged(items: list) -> list[dict[str, Any]]:
    """规范化事实/解读条目:text 排版规范化;figure.t 规范化 + 落实成 text 子串(补单位/去冗余符号)+ 丢死 figure。"""
    out: list[dict[str, Any]] = []
    for it in items:
        text = normalize_text(it.text)
        figures: list[dict[str, Any]] = []
        for f in it.figures:
            base = normalize_text(f.t)
            resolved = _resolve_fig_token(text, base) if base else None
            if resolved:
                figures.append({"t": resolved, "dir": f.dir.value})
        out.append({"tag": it.tag, "text": text, "figures": figures})
    return out


def build_reviews(hyp_rows: list[dict[str, Any]], target_date: str) -> list[Review]:
    """今日定结(held/invalidated)在前,其余 open 在后。文本经规范化。"""
    out: list[Review] = []

    def mk(r: dict[str, Any], status: ReviewStatus) -> Review:
        return Review(if_then=normalize_text(r.get("if_then", "")), status=status, note=normalize_text(r.get("note", "")))

    for r in hyp_rows:
        if r.get("resolved_date") == target_date and r.get("status") in ("held", "invalidated"):
            out.append(mk(r, ReviewStatus(r["status"])))
    for r in hyp_rows:
        if (r.get("status") or "open") == "open":
            out.append(mk(r, ReviewStatus.OPEN))
    return out


def build_view(llm: LLMBrief | None) -> ModelView:
    """单个模型的"解释层"产出 → ModelView(六层,文本经规范化)。llm 为 None 则空视图、tone 中性。"""
    b = llm or LLMBrief()
    return ModelView(
        tone=b.tone,
        headline=normalize_text(b.headline),
        facts=_norm_tagged(b.facts),
        reads=_norm_tagged(b.interpretation),
        hypotheses=[
            Hypothesis(
                if_then=normalize_text(h.if_then),
                invalidation=normalize_text(h.invalidation),
                asset=h.asset,
                direction=h.direction,
                horizon=h.horizon,
                confidence=h.confidence,
                key_factors=[normalize_text(k) for k in h.key_factors],
            )
            for h in b.hypotheses
        ],
        impacts=[Impact(asset=i.asset, watch=normalize_text(i.watch), dir=i.direction) for i in b.impact],
    )


def build_consensus(views: dict[str, ModelView]) -> list[ConsensusItem]:
    """对固定 roster 跨模型投票出代码级共识(多数方向 + 票数 + 认同数 + 多数方向均值信心)。

    <2 个模型则无共识可言(返回空,前端不显示共识行)。平票 → flat(分歧)。纯代码、抗污染。
    """
    if len(views) < 2:
        return []
    out: list[ConsensusItem] = []
    for asset in catalog.PREDICTION_TARGET_IDS:
        picks = [
            (h.direction.value, h.confidence)
            for v in views.values()
            for h in v.hypotheses
            if h.asset == asset
        ]
        if not picks:
            continue
        votes = {"up": 0, "down": 0, "flat": 0}
        for d, _ in picks:
            votes[d] = votes.get(d, 0) + 1
        top = max(votes.values())
        leaders = [d for d, c in votes.items() if c == top]
        direction = leaders[0] if len(leaders) == 1 else "flat"  # 平票 = 分歧 → flat
        confs = [c for d, c in picks if d == direction]
        out.append(
            ConsensusItem(
                asset=asset,
                direction=direction,
                votes=votes,
                n=len(picks),
                agree=votes.get(direction, 0),
                mean_confidence=round(sum(confs) / len(confs), 4) if confs else 0.0,
            )
        )
    return out


def build_brief(
    target_date: str,
    views_llm: dict[str, LLMBrief | None],
    metrics: list[Metric],
    reviews: list[Review],
    news: list[News],
    issue: int = 0,
    *,
    signals: list[Signal] | None = None,
    regime: dict[str, str] | None = None,
    price_series: dict[str, list[PricePoint]] | None = None,
) -> Brief:
    """组装单日 Brief(契约):脊柱(代码算)+ 每模型一份 view + 代码级共识。

    views_llm = {model_id: LLMBrief}(有序,[0]=主模型)。空(无 provider)时降级为单个 offline 空视图。
    """
    views = {mid: build_view(lb) for mid, lb in views_llm.items()}
    if not views:
        views = {OFFLINE_MODEL_ID: build_view(None)}  # 无 provider:单个空视图,前端走空态
    return Brief(
        date=target_date,
        weekday=weekday_cn(target_date),
        issue=issue,
        metrics=metrics,
        signals=signals or [],
        regime=regime or {},
        price_series=price_series or {},
        reviews=reviews,
        news=news,
        models=list(views.keys()),
        views=views,
        consensus=build_consensus(views),
    )


def _primary_view(brief: Brief) -> ModelView:
    """主视图(models[0]);缺失则任取其一,再不行给空视图。供 markdown/飞书等单一文本产物用。"""
    if brief.models and brief.models[0] in brief.views:
        return brief.views[brief.models[0]]
    return next(iter(brief.views.values()), ModelView())


# ── 人读 markdown ───────────────────────────────────────────────────────
def render_markdown(brief: Brief, macro: list[dict[str, Any]] | None = None) -> str:
    pv = _primary_view(brief)  # 单文本产物取主模型视图
    p: list[str] = [f"# 每日宏观简报 · {brief.date}", ""]
    if pv.headline:
        p += [f"**{pv.headline}**", ""]
    p += [f"_基调 tone:{pv.tone.value}_", ""]
    if len(brief.models) > 1:
        p += [f"_模型视图:{', '.join(brief.models)};下为主模型 {brief.models[0]}_", ""]

    p += ["## 数据快照(事实)", "| 指标 | 值 | 日变化 |", "|---|---:|---:|"]
    for m in brief.metrics:
        p.append(f"| {m.label} | {_fmt(m.value)} | {_fmt(m.change)} |")
    p.append("")

    if macro:
        p += ["## 月频宏观(背景)"] + [f"- {m['label']}:{m['value']}({m['obs_date']})" for m in macro] + [""]

    if brief.signals:
        p += ["## 技术指标(代码计算)"]
        by_group: dict[str, list[str]] = {}
        order: list[str] = []
        for s in brief.signals:
            if s.group not in by_group:
                by_group[s.group] = []
                order.append(s.group)
            by_group[s.group].append(f"{s.label} {_sig_fmt(s.unit, s.value)}")
        for g in order:
            p.append(f"- **{_SIG_GROUP_CN.get(g, g)}**:" + "; ".join(by_group[g]))
        p.append("")
    if brief.regime:
        p += ["## regime(代码判定)", "- " + "; ".join(f"{k}={v}" for k, v in brief.regime.items()), ""]

    _pdir = {"up": "↑", "down": "↓", "flat": "→"}
    if brief.consensus:
        p += ["## 跨模型共识(预测投票)"]
        for c in brief.consensus:
            split = ", ".join(f"{_pdir.get(k, k)}{v}" for k, v in c.votes.items() if v)
            p.append(
                f"- **{c.asset}** {_pdir.get(c.direction.value, '')} — {c.agree}/{c.n} 认同"
                f"(均值信心 {c.mean_confidence:.0%};投票 {split})"
            )
        p.append("")

    if pv.facts:
        p += ["## 事实层"] + [f"- {_tag_md(x.tag)}{x.text}" for x in pv.facts] + [""]
    if pv.reads:
        p += ["## 解读层(判断,非事实)"] + [f"- {_tag_md(x.tag)}{x.text}" for x in pv.reads] + [""]
    if pv.hypotheses:
        p += ["## 假设层(对固定方向的预测,可证伪)"]
        _phz = {"next_1d": "次日", "h_5d": "5日", "h_20d": "20日", "h_60d": "60日"}
        for h in pv.hypotheses:
            tag = ""
            if h.asset:
                tag = f"**{h.asset} {_pdir.get(h.direction.value, '')}{_phz.get(h.horizon.value, '')}**"
                if h.confidence:
                    tag += f"(信心 {h.confidence:.0%})"
                tag += " — "
            p.append(f"- {tag}**若**:{h.if_then}  \n  **失效条件**:{h.invalidation}")
        p.append("")
    if pv.impacts:
        p += ["## 影响层(观察点,非建议)"]
        _arrow = {"up": "↑", "down": "↓", "watch": "→"}
        for i in pv.impacts:
            p.append(f"- {_arrow.get(i.dir.value, '→')} **{i.asset}**:{i.watch}")
        p.append("")
    if not pv.facts and not pv.reads:
        p += ["> 未配置 LLM provider(或调用失败):仅产出数据快照 + 技术特征。", ""]

    if brief.reviews:
        p += ["## 假设复盘"]
        _icon = {"held": "✅ 已兑现", "invalidated": "❌ 已失效", "open": "⏳ 待观察"}
        for r in brief.reviews:
            line = f"- {_icon.get(r.status.value, r.status.value)}:{r.if_then}"
            if r.note:
                line += f" — {r.note}"
            p.append(line)
        p.append("")

    if brief.news:
        p += ["## 今日新闻(事实 / 解读 / 影响资产)"]
        for n in brief.news:
            tag = f"**[{_cat_cn(n.cat)}]** " if n.cat else ""
            assets = "、".join(n.assets) or "—"
            p.append(f"- {tag}{n.title} _({n.source})_ → 影响:{assets}")
        p.append("")

    p += [DISCLAIMER, ""]
    return "\n".join(p)


def render_text(brief: Brief) -> str:
    """飞书纯文本(取主模型视图)。"""
    pv = _primary_view(brief)
    lines = [f"【每日宏观简报 · {brief.date}】"]
    if pv.headline:
        lines.append(pv.headline)
    lines.append("— 数据 —")
    for m in brief.metrics:
        lines.append(f"{m.label}: {_fmt(m.value)}(Δ{_fmt(m.change)})")
    if pv.reads:
        lines.append("— 解读 —")
        lines += [f"· {('[' + x.tag + '] ') if x.tag else ''}{x.text}" for x in pv.reads]
    if pv.hypotheses:
        lines.append("— 可证伪假设 —")
        lines += [f"· 若 {h.if_then};失效:{h.invalidation}" for h in pv.hypotheses]
    if pv.impacts:
        lines.append("— 观察点(非建议)—")
        lines += [f"· {i.asset}: {i.watch}" for i in pv.impacts]
    if brief.reviews:
        lines.append("— 假设复盘 —")
        _icon = {"held": "✅", "invalidated": "❌", "open": "⏳"}
        lines += [f"· {_icon.get(r.status.value, '')} {r.if_then}" for r in brief.reviews[:6]]
    if brief.news:
        lines.append("— 今日新闻 —")
        for n in brief.news[:6]:
            tag = f"[{_cat_cn(n.cat)}] " if n.cat else ""
            lines.append(f"· {tag}{n.title}")
    lines.append("仅研究参考,不构成投资建议。")
    return "\n".join(lines)


# ── 聚合 briefs.json(前端接缝)──────────────────────────────────────────
def upsert_briefs_json(paths: Paths, brief: Brief, model: str) -> int:
    """写单日 briefs/<date>.json + 增量维护聚合 briefs.json(按日期 upsert,倒序,刊号按年代序)。"""
    by_date: dict[str, dict] = {}
    if paths.briefs_json.exists():
        try:
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            for b in data.get("briefs", []):
                if isinstance(b, dict) and b.get("date"):
                    by_date[b["date"]] = b
        except (ValueError, OSError):
            by_date = {}
    by_date[brief.date] = brief.to_json_obj()

    dates_asc = sorted(by_date)
    for i, d in enumerate(dates_asc, 1):
        by_date[d]["issue"] = i  # 刊号 = 年代序(最早=1),可重算
    payload = BriefsPayload(
        model=model,
        generated_at=dates_asc[-1],
        briefs=[Brief.model_validate(by_date[d]) for d in reversed(dates_asc)],
    )

    paths.briefs.mkdir(parents=True, exist_ok=True)
    (paths.briefs / f"{brief.date}.json").write_text(
        json.dumps(by_date[brief.date], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths.briefs_json.write_text(
        json.dumps(payload.to_json_obj(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(dates_asc)


_SIG_GROUP_CN = {
    "trend": "趋势", "momentum": "动量", "vol": "波动与风险", "rates": "利率与通胀",
    "dollar": "美元", "cross_asset": "跨资产相关", "range": "52周分位",
}


def _sig_fmt(unit: str, v: float) -> str:
    """按 unit 格式化技术指标(与前端 format 约定一致)。"""
    if unit == "pct":
        return f"{v * 100:+.1f}%"
    if unit == "pct0":
        return f"{v * 100:.1f}%"
    if unit == "bp":
        return f"{v:+.0f}bp"
    if unit == "z":
        return f"z={v:.2f}"
    if unit == "yield":
        return f"{v:.2f}%"
    return f"{v:.2f}"  # corr


def _tag_md(tag: str) -> str:
    """事实/解读条目的主题标签 → markdown 前缀(空标签则无前缀)。"""
    return f"**[{tag}]** " if tag else ""


def _fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _cat_cn(cat: NewsCat | None) -> str:
    rev = {v: k for k, v in _CAT_EN.items()}
    return rev.get(cat.value, "") if cat else ""
