"""观察集:逻辑指标 → 物理来源(主源 + 兜底链)+ 整批拉取。

设计要点:
- **兜底是整序列级**:某逻辑指标按链路依次尝试,第一个成功的源**提供该序列的全部历史**;
  不在同一序列里跨源逐日拼接(SPY≈SP500/10 等尺度不同,逐日混用会造成假跳变)。
  每次运行全量重拉并覆盖,故落盘的每条序列内部同源、连续。
- `kind` 驱动特征口径:价格/指数→收益率,利率/利差→bp 变化量,月频宏观→只作背景。
- `metric_kind` 非空者进前端指标表(顺序 = 本表顺序);月频宏观不进表。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from .models import MetricKind
from .sources import FetchError
from .sources.base import DATE, VALUE, Source
from .sources.fred import FredSource
from .sources.tiingo import TiingoSource
from .sources.twelvedata import TwelveDataSource
from .sources.yahoo import YahooSource

log = logging.getLogger(__name__)

# 内部 kind(驱动特征口径)
KIND_RATE = "rate"  # 利率/收益率:算 bp 变化量
KIND_SPREAD = "spread"  # 利差:算 bp 变化量
KIND_INDEX = "index"  # 指数:算收益率
KIND_PRICE = "price"  # 价格:算收益率
KIND_MACRO_M = "macro_m"  # 月频宏观:只作背景,不进滚动特征/回测


@dataclass(frozen=True)
class SourceRef:
    source: str
    symbol: str


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str  # 我们的逻辑 id(落盘/特征用)
    label: str  # 长标签(喂 prompt)
    kind: str
    chain: tuple[SourceRef, ...]  # 主源在前,兜底在后
    metric_kind: MetricKind | None = None  # 非空 = 进前端指标表
    metric_label: str = ""  # 指标表短标签
    note: str = ""


def _fred(sym: str) -> SourceRef:
    return SourceRef("fred", sym)


# ── 观察集(V1)──────────────────────────────────────────────────────────
CATALOG: tuple[SeriesSpec, ...] = (
    SeriesSpec("SP500", "标普500", KIND_INDEX, (_fred("SP500"), SourceRef("tiingo", "SPY")),
               MetricKind.INDEX, "标普500", "FRED 仅近10年;失败回退 Tiingo SPY(尺度不同,整序列级)"),
    SeriesSpec("NASDAQCOM", "纳斯达克综合指数", KIND_INDEX, (_fred("NASDAQCOM"), SourceRef("tiingo", "QQQ")),
               MetricKind.INDEX, "纳指", "回退 QQQ 口径为纳指100,非综合"),
    SeriesSpec("VIXCLS", "VIX 波动率指数", KIND_INDEX, (_fred("VIXCLS"),),
               MetricKind.INDEX, "VIX"),
    SeriesSpec("DGS2", "2年期美债收益率", KIND_RATE, (_fred("DGS2"),),
               MetricKind.YIELD, "US2Y"),
    SeriesSpec("DGS10", "10年期美债收益率", KIND_RATE, (_fred("DGS10"),),
               MetricKind.YIELD, "US10Y"),
    SeriesSpec("T10Y2Y", "2s10s 利差", KIND_SPREAD, (_fred("T10Y2Y"),),
               MetricKind.SPREAD, "2s10s"),
    SeriesSpec("DFII10", "10年期实际利率(TIPS)", KIND_RATE, (_fred("DFII10"),),
               MetricKind.YIELD, "实际10Y"),
    SeriesSpec("T10YIE", "10年期盈亏平衡通胀(通胀预期)", KIND_RATE, (_fred("T10YIE"),),
               MetricKind.YIELD, "通胀预期"),
    SeriesSpec("DTWEXBGS", "广义美元指数(贸易加权)", KIND_INDEX, (_fred("DTWEXBGS"),),
               MetricKind.INDEX, "广义美元"),
    SeriesSpec("UUP", "窄口径美元指数(UUP 代理)", KIND_INDEX, (SourceRef("tiingo", "UUP"),),
               None, "", "ETF 代理:只用收益率/趋势/标准化,不取绝对价位"),
    SeriesSpec("XAUUSD", "黄金现货", KIND_PRICE,
               (SourceRef("twelvedata", "XAU/USD"), SourceRef("tiingo", "GLD"), SourceRef("yahoo", "GC=F")),
               MetricKind.PRICE, "黄金", "主 XAU/USD 现货;回退 GLD/期货"),
    # 月频宏观:只作背景(不进滚动特征/回测)
    SeriesSpec("CPILFESL", "核心 CPI", KIND_MACRO_M, (_fred("CPILFESL"),)),
    SeriesSpec("UNRATE", "失业率", KIND_MACRO_M, (_fred("UNRATE"),)),
    SeriesSpec("PAYEMS", "非农就业", KIND_MACRO_M, (_fred("PAYEMS"),)),
    SeriesSpec("FEDFUNDS", "联邦基金利率", KIND_MACRO_M, (_fred("FEDFUNDS"),)),
)

SPEC_BY_ID: dict[str, SeriesSpec] = {s.series_id: s for s in CATALOG}
DAILY_IDS: tuple[str, ...] = tuple(s.series_id for s in CATALOG if s.kind != KIND_MACRO_M)
MACRO_IDS: tuple[str, ...] = tuple(s.series_id for s in CATALOG if s.kind == KIND_MACRO_M)
DISPLAY_METRICS: tuple[SeriesSpec, ...] = tuple(s for s in CATALOG if s.metric_kind is not None)


def build_sources(settings) -> dict[str, Source]:
    """按配置构造各源实例(缺 key 的源仍构造,fetch 时抛 FetchError 自动降级)。"""
    return {
        "fred": FredSource(settings.fred_api_key),
        "twelvedata": TwelveDataSource(settings.twelvedata_api_key),
        "tiingo": TiingoSource(settings.tiingo_api_token),
        "yahoo": YahooSource(),
    }


def fetch_series(
    spec: SeriesSpec, sources: dict[str, Source], start: str | None, end: str | None
) -> tuple[pd.DataFrame, str] | None:
    """按兜底链拉取单个逻辑序列。返回 (帧, 实际命中源名);全失败返回 None。"""
    for ref in spec.chain:
        src = sources.get(ref.source)
        if src is None:
            continue
        try:
            df = src.fetch(ref.symbol, start, end)
        except FetchError as e:
            log.warning("series %s: source '%s' (%s) failed: %s", spec.series_id, ref.source, ref.symbol, e)
            continue
        if df is not None and not df.empty:
            if ref is not spec.chain[0]:
                log.warning("series %s: degraded to fallback source '%s'", spec.series_id, ref.source)
            return df, ref.source
    return None


def fetch_all(
    sources: dict[str, Source], start: str | None, end: str | None, specs: tuple[SeriesSpec, ...] = CATALOG
) -> pd.DataFrame:
    """拉取整个观察集 → tidy 长表 [date, series_id, value, source](升序)。"""
    frames: list[pd.DataFrame] = []
    for spec in specs:
        res = fetch_series(spec, sources, start, end)
        if res is None:
            log.warning("series %s: all sources failed, skipped", spec.series_id)
            continue
        df, used = res
        frames.append(df.assign(series_id=spec.series_id, source=used))
    cols = [DATE, "series_id", VALUE, "source"]
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)[cols]
