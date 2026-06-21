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

from . import catalog, features, hypotheses as hyp, news as news_mod, regime, render
from .config import PATHS, Settings, get_settings
from .deliver.feishu import push_text
from .llm import generate_brief, select_provider
from .llm.prompt import build_feature_block
from .models import Brief
from .store import RawStore

log = logging.getLogger(__name__)

_MODEL_DISPLAY = {
    "anthropic": "Claude", "openai": "OpenAI", "deepseek": "DeepSeek",
    "minimax": "MiniMax", "moonshot": "Moonshot", "zhipu": "Zhipu", "openai-compat": "LLM",
}


def _today() -> str:
    return datetime.date.today().isoformat()


def _model_name() -> str:
    p = select_provider()
    return _MODEL_DISPLAY.get(getattr(p, "name", ""), getattr(p, "name", "LLM")) if p else "offline"


def _start_date(target: str, years: int) -> str:
    y, m, d = (int(x) for x in target.split("-"))
    return datetime.date(y - years, m, d).isoformat()


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
    """在 long 帧上算特征 → LLM → 假设复盘 → 新闻 → 组装 Brief。返回 (brief, 附属物)。

    news_mode: 'live'=抓当前 RSS(今日报告);'none'=不带新闻(历史回填,避免预知未来,v2)。
    """
    wide = features.build_wide(long_df)
    feat = features.compute_features(wide)
    snap = features.snapshot_at(feat, target_date)
    reg = regime.derive(snap)
    macro = features.macro_latest(long_df, target_date)

    metrics = render.build_metrics(long_df, target_date)
    metrics_prompt = [{"label": m.label, "value": m.value, "change": m.change, "kind": m.kind.value} for m in metrics]
    block = build_feature_block(target_date, metrics_prompt, snap, reg, macro)

    # 1) 四层简报
    linkage = PATHS.linkage_map.read_text(encoding="utf-8") if PATHS.linkage_map.exists() else ""
    try:
        llm_brief = generate_brief(block, linkage)
    except Exception as e:  # noqa: BLE001 — LLM 失败降级,不阻断
        log.warning("LLM 生成失败,退回特征层: %s", e)
        llm_brief = None

    # 2) 假设追踪:复盘往日 open(不拿当天数据自我验证),登记今天新假设
    hyp_rows = hyp.load(PATHS.hypotheses_csv)
    try:
        open_hyps = [h for h in hyp.open_items(hyp_rows) if h.get("created_date") != target_date]
        reviews_raw = hyp.review(open_hyps, block)
        hyp.apply_reviews(open_hyps, reviews_raw, target_date)
        if llm_brief and llm_brief.hypotheses:
            hyp.record_new(
                hyp_rows, target_date,
                [{"if_then": h.if_then, "invalidation": h.invalidation} for h in llm_brief.hypotheses],
            )
        hyp.save(PATHS.hypotheses_csv, hyp_rows)
    except Exception as e:  # noqa: BLE001
        log.warning("假设追踪失败,跳过: %s", e)
    reviews = render.build_reviews(hyp_rows, target_date)

    # 3) 新闻(live 才抓;none = 历史回填不带新闻)
    merged: list[dict[str, Any]] = []
    settings = get_settings()
    if news_mode == "live" and not settings.news_disabled:
        # fetch 与 classify 解耦:抓到了就展示;分类(LLM)失败只降级为「未分类新闻」,
        # 绝不因分类报错把已抓到的新闻(都带链接)一并丢掉。
        try:
            items = news_mod.fetch_news()
        except Exception as e:  # noqa: BLE001
            items = []
            log.warning("新闻抓取失败,跳过: %s", e)
        if items:
            classified = None
            try:
                classified = news_mod.classify(items)
            except Exception as e:  # noqa: BLE001
                log.warning("新闻分类失败,展示未分类新闻: %s", e)
            merged = _merge_news(items, classified)
            log.info("抓取 %s 条新闻(%s)", len(items), "已分类" if classified else "未分类")

    signals = render.build_signals(snap)
    brief = render.build_brief(
        target_date, llm_brief, metrics, reviews, render.build_news(merged),
        signals=signals, regime=reg,
    )
    if persist_features:
        try:
            RawStore(PATHS).write_features(target_date, pd.DataFrame([{"date": target_date, **snap}]))
        except Exception as e:  # noqa: BLE001
            log.warning("特征快照落盘失败,跳过: %s", e)
    return brief, {"macro": macro, "feature_block": block}


def write_outputs(brief: Brief, macro: list[dict[str, Any]]) -> None:
    """写 markdown + briefs.json + 推飞书。"""
    PATHS.briefs.mkdir(parents=True, exist_ok=True)
    md_path = PATHS.briefs / f"{brief.date}.md"
    md_path.write_text(render.render_markdown(brief, macro), encoding="utf-8")
    log.info("简报已存: %s", md_path)

    try:
        days = render.upsert_briefs_json(PATHS, brief, _model_name())
        log.info("已导出 briefs.json(共 %s 天)", days)
    except Exception as e:  # noqa: BLE001
        log.warning("导出 briefs.json 失败: %s", e)

    try:
        pushed = push_text(render.render_text(brief))
        log.info("已推送飞书" if pushed else "未配置 FEISHU_WEBHOOK,跳过推送(已存 md)")
    except Exception as e:  # noqa: BLE001
        log.warning("飞书推送失败(已存 md): %s", e)


def run(target_date: str | None = None, history_years: int = 12, news_mode: str = "live") -> Brief:
    """完整跑一天:拉数→落盘→报告→写产物。返回 Brief。"""
    settings = get_settings()
    target = target_date or _today()
    log.info("生成简报 target_date=%s", target)
    long_df = fetch_and_store(settings, target, history_years)
    brief, extra = build_report(long_df, target, news_mode=news_mode)
    write_outputs(brief, extra["macro"])
    return brief
