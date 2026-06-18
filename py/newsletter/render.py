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
from .models import (
    Brief,
    BriefsPayload,
    Dir,
    Hypothesis,
    Impact,
    LLMBrief,
    Metric,
    News,
    NewsCat,
    Review,
    ReviewStatus,
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
            )
        )
    return out


def build_news(merged: list[dict[str, Any]]) -> list[News]:
    out: list[News] = []
    for n in merged or []:
        cat_cn = n.get("category")
        cat = NewsCat(_CAT_EN[cat_cn]) if cat_cn in _CAT_EN else None
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


def build_reviews(hyp_rows: list[dict[str, Any]], target_date: str) -> list[Review]:
    """今日定结(held/invalidated)在前,其余 open 在后。"""
    out: list[Review] = []
    for r in hyp_rows:
        if r.get("resolved_date") == target_date and r.get("status") in ("held", "invalidated"):
            out.append(Review(if_then=r.get("if_then", ""), status=ReviewStatus(r["status"]), note=r.get("note", "")))
    for r in hyp_rows:
        if (r.get("status") or "open") == "open":
            out.append(Review(if_then=r.get("if_then", ""), status=ReviewStatus.OPEN, note=r.get("note", "")))
    return out


def build_brief(
    target_date: str,
    llm: LLMBrief | None,
    metrics: list[Metric],
    reviews: list[Review],
    news: list[News],
    issue: int = 0,
) -> Brief:
    """组装单日 Brief(契约)。llm 为 None(无 provider)时四层留空、tone 中性。"""
    b = llm or LLMBrief()
    return Brief(
        date=target_date,
        weekday=weekday_cn(target_date),
        issue=issue,
        tone=b.tone,
        headline=b.headline,
        metrics=metrics,
        facts=b.facts,
        reads=b.interpretation,
        hypotheses=[Hypothesis(if_then=h.if_then, invalidation=h.invalidation) for h in b.hypotheses],
        impacts=[Impact(asset=i.asset, watch=i.watch, dir=i.direction) for i in b.impact],
        reviews=reviews,
        news=news,
    )


# ── 人读 markdown ───────────────────────────────────────────────────────
def render_markdown(brief: Brief, macro: list[dict[str, Any]] | None = None) -> str:
    p: list[str] = [f"# 每日宏观简报 · {brief.date}", ""]
    if brief.headline:
        p += [f"**{brief.headline}**", ""]
    p += [f"_基调 tone:{brief.tone.value}_", ""]

    p += ["## 数据快照(事实)", "| 指标 | 值 | 日变化 |", "|---|---:|---:|"]
    for m in brief.metrics:
        p.append(f"| {m.label} | {_fmt(m.value)} | {_fmt(m.change)} |")
    p.append("")

    if macro:
        p += ["## 月频宏观(背景)"] + [f"- {m['label']}:{m['value']}({m['obs_date']})" for m in macro] + [""]

    if brief.facts:
        p += ["## 事实层"] + [f"- {x}" for x in brief.facts] + [""]
    if brief.reads:
        p += ["## 解读层(判断,非事实)"] + [f"- {x}" for x in brief.reads] + [""]
    if brief.hypotheses:
        p += ["## 假设层(可证伪)"]
        for h in brief.hypotheses:
            p.append(f"- **若**:{h.if_then}  \n  **失效条件**:{h.invalidation}")
        p.append("")
    if brief.impacts:
        p += ["## 影响层(观察点,非建议)"]
        _arrow = {"up": "↑", "down": "↓", "watch": "→"}
        for i in brief.impacts:
            p.append(f"- {_arrow.get(i.dir.value, '→')} **{i.asset}**:{i.watch}")
        p.append("")
    if not brief.facts and not brief.reads:
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
    """飞书纯文本。"""
    lines = [f"【每日宏观简报 · {brief.date}】"]
    if brief.headline:
        lines.append(brief.headline)
    lines.append("— 数据 —")
    for m in brief.metrics:
        lines.append(f"{m.label}: {_fmt(m.value)}(Δ{_fmt(m.change)})")
    if brief.reads:
        lines.append("— 解读 —")
        lines += [f"· {x}" for x in brief.reads]
    if brief.hypotheses:
        lines.append("— 可证伪假设 —")
        lines += [f"· 若 {h.if_then};失效:{h.invalidation}" for h in brief.hypotheses]
    if brief.impacts:
        lines.append("— 观察点(非建议)—")
        lines += [f"· {i.asset}: {i.watch}" for i in brief.impacts]
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


def _fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _cat_cn(cat: NewsCat | None) -> str:
    rev = {v: k for k, v in _CAT_EN.items()}
    return rev.get(cat.value, "") if cat else ""
