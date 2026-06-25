"""编排:拉数 → 落盘 → 特征 → regime → LLM → 渲染 → 输出(md / briefs.json / 飞书)。

`target_date` 贯穿全链路(默认今天),为 v2 历史回放/回测就位。拆成三段便于复用:
- `fetch_and_store`:拉全量原始数据并落盘快照(归档上一份)。
- `build_report`:在给定 long 帧上算特征 → LLM → 组装 Brief(纯计算,不落盘,可被回填循环复用)。
- `run`:串起来并写出全部产物。
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import pandas as pd

from . import (
    catalog,
    evaluate,
    factors as factors_mod,
    features,
    market_calendar,
    news as news_mod,
    predictions as pred,
    regime,
    render,
)
from .config import PATHS, Settings, get_settings
from .deliver.feishu import push_text
from .llm import generate_briefs
from .llm.prompt import build_feature_block
from .models import Brief
from .news.cache import ExtractCache
from .store import RawStore

log = logging.getLogger(__name__)

_MODEL_DISPLAY = {
    "anthropic": "Claude", "openai": "OpenAI", "deepseek": "DeepSeek",
    "minimax": "MiniMax", "moonshot": "Moonshot", "zhipu": "Zhipu", "openai-compat": "LLM",
}


def _today() -> str:
    return datetime.date.today().isoformat()


def _models_label(names: list[str]) -> str:
    """模型 id 列表 → 人读标签(用于 briefs.json payload.model);空则 offline。"""
    return " + ".join(_MODEL_DISPLAY.get(n, n) for n in names) if names else "offline"


def _start_date(target: str, years: int) -> str:
    y, m, d = (int(x) for x in target.split("-"))
    return datetime.date(y - years, m, d).isoformat()


def _news_window(target_date: str, news_mode: str) -> tuple[str | None, str | None]:
    """新闻检索时间窗。live=最新(None);backfill=回放日前 3 天 → 当日(不取未来新闻)。"""
    if news_mode != "backfill":
        return None, None
    y, m, d = (int(x) for x in target_date.split("-"))
    start = (datetime.date(y, m, d) - datetime.timedelta(days=3)).isoformat()
    return start, target_date


def _effective_news_mode(news_mode: str, target_date: str) -> str:
    """历史回放强制 backfill —— 杜绝"先知泄漏"。

    live 只该用于"当天/未来"(抓最新,含无法时间过滤的 RSS)。若拿 live 跑一个**过去**的
    target_date,会抓到运行日(=未来)的新闻挂到历史简报上 → 先知泄漏。所以过去日自动降级
    backfill:TheNewsAPI 带时间窗(published_before<回放日,实测排他边界,不含当天及之后)+ 去掉 RSS。
    none/backfill 保持原样。
    """
    if news_mode == "live" and target_date < _today():
        return "backfill"
    return news_mode


def fetch_and_store(settings: Settings, target_date: str, history_years: int = 12) -> pd.DataFrame:
    """拉取观察集全量(start..target),落盘 latest 快照(归档上一份)。返回 long 帧。"""
    sources = catalog.build_sources(settings)
    long_df = catalog.fetch_all(sources, _start_date(target_date, history_years), target_date)
    if long_df.empty:
        raise RuntimeError("所有数据源均失败,未取到任何观测")
    RawStore(PATHS).write_snapshot(long_df, pull_date=target_date)
    return long_df


def _merge_news(items: list, classified: list | None) -> list[dict[str, Any]]:
    """把分类结果贴回原始新闻:优先按模型回填的 index(从 1)对齐,标题兜底;两者皆不中则未分类。"""
    by_index, by_title = {}, {}
    for c in classified or []:
        if not isinstance(c, dict):
            continue
        try:
            idx = int(c.get("index"))
        except (TypeError, ValueError):
            idx = None
        if idx is not None and 1 <= idx <= len(items):
            by_index.setdefault(idx, c)
        t = (c.get("title") or "").strip().lower()
        if t:
            by_title.setdefault(t, c)
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        d: dict[str, Any] = {"source": it.source, "title": it.title, "link": it.link}
        c = by_index.get(i + 1) or by_title.get(it.title.strip().lower())
        if c:
            d.update(
                category=c.get("category"),
                summary=c.get("summary"),
                affected_assets=c.get("affected_assets"),
                note=c.get("note"),
                direction=c.get("direction"),
            )
        out.append(d)
    return out


def build_report(
    long_df: pd.DataFrame,
    target_date: str,
    *,
    news_mode: str = "live",
    persist_features: bool = True,
) -> tuple[Brief, dict[str, Any]]:
    """在 long 帧上算特征 + 因子 → 新闻 → LLM(A/B 两臂)→ 预测账本 + 评估 → 组装 Brief。返回 (brief, 附属物)。

    news_mode:'live'=抓最新(RSS+TheNewsAPI,今日);'backfill'=抓回放日历史新闻(TheNewsAPI);'none'=不带新闻。
    有新闻时产 A/B 两臂(A=纯价格因子 / B=加新闻),简报用 B;无新闻则单臂。
    """
    wide = features.build_wide(long_df)
    feat = features.compute_features(wide)
    snap = features.snapshot_at(feat, target_date)
    reg = regime.derive(snap)
    af_by_sid = factors_mod.compute_factors(snap)  # 量化因子层(因子打分 + 代码基线 + 波动率预测)
    macro = features.macro_latest(long_df, target_date)

    metrics = render.build_metrics(long_df, target_date)
    metrics_prompt = [{"label": m.label, "value": m.value, "change": m.change, "kind": m.kind.value} for m in metrics]
    block_base = build_feature_block(target_date, metrics_prompt, snap, reg, macro, factors=af_by_sid)  # A 臂:纯价格因子

    source = "forward" if target_date >= _today() else "backfill"  # 回放历史日 = backfill(含记忆污染);新闻入库也用它打标

    # 1) 新闻(live/backfill 都抓;none 不抓):抓 → 抽全文 → 分类 → 入语料库 → 截面+滚动特征(喂 B 臂)
    merged: list[dict[str, Any]] = []
    news_features: dict[str, Any] = {}
    settings = get_settings()
    if news_mode != "none" and not settings.news_disabled:
        eff_mode = _effective_news_mode(news_mode, target_date)  # 历史日 live→backfill,防先知泄漏
        if eff_mode != news_mode:
            log.info("target_date %s 为历史日,新闻 %s→%s(时间窗,防先知泄漏)", target_date, news_mode, eff_mode)
        try:
            start, end = _news_window(target_date, eff_mode)
            items = news_mod.fetch_news(eff_mode, start=start, end=end)
            items = news_mod.enrich(items, cache=ExtractCache(PATHS.news_cache))  # 抓全文 + 缓存,死链丢弃
        except Exception as e:  # noqa: BLE001
            items = []
            log.warning("新闻抓取/抽取失败,跳过: %s", e)
        if items:
            classified = None
            try:
                classified = news_mod.classify(items)  # fetch/classify 解耦:分类失败仍展示未分类
            except Exception as e:  # noqa: BLE001
                log.warning("新闻分类失败,展示未分类新闻: %s", e)
            merged = _merge_news(items, classified)
            try:  # 入语料库(article-level parquet,uuid 幂等;v1.8)
                store = news_mod.NewsStore(PATHS.news)
                n_in = store.upsert(news_mod.build_article_records(items, classified, source_tag=source))
                log.info("新闻入库 %s 条 → %s", n_in, PATHS.news)
            except Exception as e:  # noqa: BLE001
                log.warning("新闻入库失败,跳过: %s", e)
            try:
                news_features = news_mod.compute_news_features(items, classified)  # 当天截面
            except Exception as e:  # noqa: BLE001
                log.warning("新闻截面特征失败,跳过: %s", e)
            try:  # 滚动时序 + 情绪—价格背离(从语料库历史;P5/P4)。只读到 target_date(因果)
                px_ret = {sid: snap.get(f"{sid}_ret_20") for sid in ("NASDAQCOM", "XAUUSD", "DTWEXBGS")
                          if snap.get(f"{sid}_ret_20") is not None}
                trends = news_mod.compute_news_trends(
                    news_mod.NewsStore(PATHS.news).load(end=target_date), target_date, price_returns=px_ret)
                if trends:
                    news_features["trends"] = trends
            except Exception as e:  # noqa: BLE001
                log.warning("新闻滚动趋势失败,跳过: %s", e)
            log.info("新闻 %s 条(%s),特征资产 %s", len(items),
                     "已分类" if classified else "未分类", list(news_features.get("byAsset", {})))

    # 2) 四层简报 A/B:B = 纯价格因子 + 新闻(主视图);A = 纯价格因子(影子臂,仅记账对照)
    linkage = PATHS.linkage_map.read_text(encoding="utf-8") if PATHS.linkage_map.exists() else ""
    block_b = (
        build_feature_block(target_date, metrics_prompt, snap, reg, macro, factors=af_by_sid, news_features=news_features)
        if news_features else block_base
    )
    try:
        views_llm = generate_briefs(block_b, linkage)  # 主视图(无新闻时即纯因子)
    except Exception as e:  # noqa: BLE001 — LLM 整体失败降级,不阻断
        log.warning("LLM 生成失败,退回特征层: %s", e)
        views_llm = {}
    views_llm_a: dict[str, Any] = {}
    if news_features:
        try:
            views_llm_a = generate_briefs(block_base, linkage)  # A 影子臂(无新闻)
        except Exception as e:  # noqa: BLE001
            log.warning("A 臂生成失败,跳过 A 臂: %s", e)

    # 3) 预测账本:记 A/B(有新闻则两臂,否则单记无臂)+ 到期结算 + LLM 复盘(source 见上,新闻入库共用)
    pred_rows = pred.load(PATHS.predictions_csv)
    try:
        if news_features:
            pred.record(pred_rows, target_date, views_llm, factors=af_by_sid, arm="B", source=source)
            pred.record(pred_rows, target_date, views_llm_a, factors=af_by_sid, arm="A", source=source)
        else:
            pred.record(pred_rows, target_date, views_llm, factors=af_by_sid, arm="", source=source)
        newly = pred.backfill(pred_rows, long_df, target_date)  # 代码算到期项真实走势 + 命中
        pred.review(newly)  # LLM 给本次新结算的写一句复盘叙述
        pred.save(PATHS.predictions_csv, pred_rows)
    except Exception as e:  # noqa: BLE001
        log.warning("预测追踪失败,跳过: %s", e)
        pred_rows = pred.load(PATHS.predictions_csv)  # 出错时仍读最新账本供实际结果回填展示

    # 3b) 评估层:技能 vs 基线 + 校准 + Brier(按 A/B 臂)→ scorecard.json(失败不阻断)
    try:
        evaluate.write_scorecard(pred_rows, long_df)
    except Exception as e:  # noqa: BLE001
        log.warning("评估层 scorecard 生成失败,跳过: %s", e)

    signals = render.build_signals(snap)
    price_series = render.build_price_series(long_df, target_date)
    factors_view = render.build_factors(af_by_sid)
    brief = render.build_brief(
        target_date, views_llm, metrics, [], render.build_news(merged),  # reviews 已停用(改预测账本)
        signals=signals, regime=reg, price_series=price_series, factors=factors_view,
    )
    if persist_features:
        try:
            RawStore(PATHS).write_features(target_date, pd.DataFrame([{"date": target_date, **snap}]))
        except Exception as e:  # noqa: BLE001
            log.warning("特征快照落盘失败,跳过: %s", e)
    return brief, {"macro": macro, "feature_block": block_b, "pred_rows": pred_rows}


def write_outputs(
    brief: Brief, macro: list[dict[str, Any]], pred_rows: list[dict] | None = None, *, push: bool = True
) -> None:
    """写 markdown + briefs.json +(可选)推飞书。pred_rows = 预测账本(回填实际结果进所有保留简报)。

    push=False:区间重生成时用,避免把一堆历史简报推到飞书。
    """
    PATHS.briefs.mkdir(parents=True, exist_ok=True)
    md_path = PATHS.briefs / f"{brief.date}.md"
    md_path.write_text(render.render_markdown(brief, macro), encoding="utf-8")
    log.info("简报已存: %s", md_path)

    try:
        days = render.upsert_briefs_json(PATHS, brief, _models_label(brief.models), pred_rows)
        log.info("已导出 briefs.json(共 %s 天)", days)
    except Exception as e:  # noqa: BLE001
        log.warning("导出 briefs.json 失败: %s", e)

    if not push:
        return
    try:
        pushed = push_text(render.render_text(brief))
        log.info("已推送飞书" if pushed else "未配置 FEISHU_WEBHOOK,跳过推送(已存 md)")
    except Exception as e:  # noqa: BLE001
        log.warning("飞书推送失败(已存 md): %s", e)


_TRADING_REF = "NASDAQCOM"  # 判交易日的参考股指(该日有观测=交易日)


def _write_closed(brief: Brief) -> None:
    """休市 / 无数据日:只写 md + upsert briefs.json(不记预测、不推飞书)。"""
    PATHS.briefs.mkdir(parents=True, exist_ok=True)
    (PATHS.briefs / f"{brief.date}.md").write_text(render.render_markdown(brief), encoding="utf-8")
    try:
        days = render.upsert_briefs_json(PATHS, brief, "—", None)
        log.info("已导出 briefs.json(共 %s 天)", days)
    except Exception as e:  # noqa: BLE001
        log.warning("导出 briefs.json 失败: %s", e)


def _run_trading_or_nodata(
    long_df: pd.DataFrame, target_date: str, *, news_mode: str = "live", push: bool = True
) -> Brief:
    """已知是工作日且非节假日:有观测→完整 brief;无观测→no_data 空 brief。"""
    if not features.has_observation(long_df, _TRADING_REF, target_date):
        brief = render.build_closed_brief(target_date, "no_data", "")
        _write_closed(brief)
        log.warning("%s 应为交易日但无 %s 观测,产出 no_data brief", target_date, _TRADING_REF)
        return brief
    brief, extra = build_report(long_df, target_date, news_mode=news_mode)
    write_outputs(brief, extra["macro"], extra.get("pred_rows"), push=push)
    return brief


def run(target_date: str | None = None, history_years: int = 12, news_mode: str = "live") -> Brief:
    """完整跑一天。周末/节假日直接产空 closed brief(不拉数);否则拉数→报告→写产物。"""
    settings = get_settings()
    target = target_date or _today()
    reason = market_calendar.nontrading_reason(target)
    if reason:  # 周末 / 节假日:无需拉数,直接空 brief
        log.info("生成简报 target_date=%s(休市:%s)", target, reason)
        brief = render.build_closed_brief(target, "closed", reason)
        _write_closed(brief)
        return brief
    log.info("生成简报 target_date=%s", target)
    long_df = fetch_and_store(settings, target, history_years)
    return _run_trading_or_nodata(long_df, target, news_mode=news_mode)


def run_range(
    start: str, end: str | None = None, history_years: int = 12, news_mode: str = "live"
) -> dict[str, int]:
    """区间重生成:[start, end] 每个**日历日**各产一份 brief(交易日完整 / 非交易日空)。

    价格**只 fetch 一次**(到 end),循环复用 → 快;新闻仍按日抓(历史日自动走 backfill 时间窗,防先知)。
    end 默认 = 参考股指最新有观测的日(避免给"今天数据未发布"造一堆 no_data 尾巴)。
    返回 {trading, closed, no_data, days} 计数。
    """
    settings = get_settings()
    fetch_end = end or _today()
    long_df = fetch_and_store(settings, fetch_end, history_years)  # 一次拉到 fetch_end
    if end is None:
        end = features.last_observation_date(long_df, _TRADING_REF) or fetch_end  # 截到最新有数据日
    days = market_calendar.iter_days(start, end)
    counts = {"trading": 0, "closed": 0, "no_data": 0, "days": len(days)}
    log.info("区间重生成 %s → %s,共 %s 个日历日", start, end, len(days))
    for d in days:
        reason = market_calendar.nontrading_reason(d)
        if reason:
            brief = render.build_closed_brief(d, "closed", reason)
            _write_closed(brief)
            counts["closed"] += 1
        else:
            brief = _run_trading_or_nodata(long_df, d, news_mode=news_mode, push=False)
            counts[brief.session] += 1
        tag = brief.session + (f"/{brief.closed_reason}" if brief.closed_reason else "")
        log.info("  %s → %s", d, tag)
    log.info("区间完成:trading=%(trading)s closed=%(closed)s no_data=%(no_data)s", counts)
    return counts
