"""技术特征层(pandas)。

原则:
- **代码算数字,LLM 只解释**(强制分层)。
- **因果**:全部用滚动窗口(只看过去)。在全历史上算一次,任意 target_date 取对应行即可,
  绝不偷看未来——这也是 v2 回测 point-in-time 的基础。
- **统一交易日历**:先把各序列 reindex 到工作日网格并前向填充(黄金含周末点、节假日无值),
  保证「N 日」口径在各序列一致;再算特征。
- 价格/指数算收益率,利率/利差算 bp 变化量;月频宏观不进特征(只作背景)。

精选特征(非越多越好):趋势(MA/相对MA200)、动量(收益率/变化量)、风险(年化波动/回撤/
VIX z/百分位)、利率·通胀(变化量、盈亏平衡)、美元(广义 vs 窄口径背离)、跨资产 60 日相关、
52 周区间百分位。
"""

from __future__ import annotations

import math

import pandas as pd

from . import catalog
from .config import WINDOWS
from .sources.base import DATE, VALUE

_SQRT252 = math.sqrt(252.0)


# ── 基础滚动算子(min_periods 容忍历史早期不足)──────────────────────────
def _mp(w: int) -> int:
    return max(2, w // 2)


def _returns(s: pd.Series, w: int) -> pd.Series:
    return s.pct_change(w, fill_method=None)


def _changes_bp(s: pd.Series, w: int) -> pd.Series:
    """利率类变化量,单位 bp(序列以 % 计,diff×100)。"""
    return s.diff(w) * 100.0


def _ma(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=_mp(w)).mean()


def _vol_ann(s: pd.Series, w: int) -> pd.Series:
    return s.pct_change(fill_method=None).rolling(w, min_periods=_mp(w)).std() * _SQRT252


def _drawdown(s: pd.Series, w: int) -> pd.Series:
    return s / s.rolling(w, min_periods=_mp(w)).max() - 1.0


def _zscore(s: pd.Series, w: int) -> pd.Series:
    m = s.rolling(w, min_periods=_mp(w)).mean()
    sd = s.rolling(w, min_periods=_mp(w)).std()
    return (s - m) / sd


def _range_pct(s: pd.Series, w: int) -> pd.Series:
    lo = s.rolling(w, min_periods=_mp(w)).min()
    hi = s.rolling(w, min_periods=_mp(w)).max()
    return (s - lo) / (hi - lo)


def _delta(s: pd.Series, kind: str) -> pd.Series:
    """每日增量:价格/指数用收益率,利率/利差用一阶差(供相关性)。"""
    return s.diff() if kind in (catalog.KIND_RATE, catalog.KIND_SPREAD) else s.pct_change(fill_method=None)


# ── 宽表构建 ────────────────────────────────────────────────────────────
def build_wide(long_df: pd.DataFrame, ids: tuple[str, ...] = catalog.DAILY_IDS) -> pd.DataFrame:
    """long → 宽表(index=工作日,columns=series_id 的电平),reindex 工作日网格 + 前向填充。"""
    sub = long_df[long_df["series_id"].isin(ids)]
    wide = sub.pivot_table(index=DATE, columns="series_id", values=VALUE, aggfunc="last")
    wide.index = pd.to_datetime(wide.index)
    wide = wide.sort_index()
    if wide.empty:
        return wide
    cal = pd.bdate_range(wide.index.min(), wide.index.max())
    return wide.reindex(cal).ffill()


# ── 特征帧 ──────────────────────────────────────────────────────────────
def compute_features(wide: pd.DataFrame) -> pd.DataFrame:
    """在宽表上算全部特征,返回 index=日期、列=`<series>_<feat>` 的特征帧(因果)。"""
    cols: dict[str, pd.Series] = {}
    present = [c for c in wide.columns if c in catalog.SPEC_BY_ID]

    for sid in present:
        s = wide[sid]
        kind = catalog.SPEC_BY_ID[sid].kind
        cols[f"{sid}_level"] = s
        cols[f"{sid}_z_{WINDOWS.zscore}"] = _zscore(s, WINDOWS.zscore)

        if kind in (catalog.KIND_PRICE, catalog.KIND_INDEX):
            for w in WINDOWS.returns:
                cols[f"{sid}_ret_{w}"] = _returns(s, w)
            for w in WINDOWS.ma:
                cols[f"{sid}_ma_{w}"] = _ma(s, w)
            cols[f"{sid}_px_vs_ma200"] = s / _ma(s, 200) - 1.0
            cols[f"{sid}_above_ma200"] = (s > _ma(s, 200)).astype("float")
            for w in WINDOWS.vol:
                cols[f"{sid}_vol_{w}"] = _vol_ann(s, w)
            for w in WINDOWS.drawdown:
                cols[f"{sid}_maxdd_{w}"] = _drawdown(s, w)
            cols[f"{sid}_rangepct_{WINDOWS.range_pct}"] = _range_pct(s, WINDOWS.range_pct)
        elif kind in (catalog.KIND_RATE, catalog.KIND_SPREAD):
            for w in WINDOWS.changes:
                cols[f"{sid}_chg_{w}"] = _changes_bp(s, w)

    # 跨资产 60 日相关(用每日增量)
    cw = WINDOWS.corr
    for a, b in (("SP500", "DGS10"), ("SP500", "VIXCLS"), ("XAUUSD", "DFII10"), ("XAUUSD", "DTWEXBGS")):
        if a in present and b in present:
            da = _delta(wide[a], catalog.SPEC_BY_ID[a].kind)
            db = _delta(wide[b], catalog.SPEC_BY_ID[b].kind)
            cols[f"corr_{a}_{b}_{cw}"] = da.rolling(cw, min_periods=_mp(cw)).corr(db)

    # 美元:广义 vs 窄口径(UUP 代理)背离 —— 用收益率之差,不碰绝对价位
    if "DTWEXBGS" in present and "UUP" in present:
        for w in (20, 60):
            cols[f"usd_broad_vs_narrow_div_{w}"] = _returns(wide["DTWEXBGS"], w) - _returns(wide["UUP"], w)

    feat = pd.DataFrame(cols, index=wide.index)
    return feat


def snapshot_at(feat: pd.DataFrame, target_date: str) -> dict[str, float]:
    """取 target_date(或其前最近交易日)那一行的特征,丢弃 NaN。"""
    ts = pd.Timestamp(target_date)
    rows = feat.loc[feat.index <= ts]
    if rows.empty:
        return {}
    row = rows.iloc[-1]
    return {k: float(v) for k, v in row.items() if pd.notna(v)}


def metric_spark(long_df: pd.DataFrame, sid: str, target_date: str, n: int = 20) -> list[float]:
    """某序列截至 target_date 的最近 n 个**真实观测电平**(因果),供前端指标表画 sparkline。

    只看 <= target_date 的真实观测点(非 ffill),与 metric_level_change 同口径;不足 n 个则全给。
    """
    sub = long_df[(long_df["series_id"] == sid) & (long_df[DATE] <= target_date)].sort_values(DATE)
    vals = sub[VALUE].tolist()
    return [round(float(v), 4) for v in vals[-n:]]


def price_series(long_df: pd.DataFrame, sid: str, target_date: str, n: int = 30) -> list[dict[str, object]]:
    """某序列截至 target_date 的最近 n 个**真实观测点**(带日期,因果),供前端 30 日价格大图。

    返回 [{date, value}, ...](升序,末点=当日真实值);不足 n 个则全给。与 metric_spark 同口径但带 date。
    """
    sub = long_df[(long_df["series_id"] == sid) & (long_df[DATE] <= target_date)].sort_values(DATE)
    tail = sub.tail(n)
    return [{"date": str(d), "value": round(float(v), 4)} for d, v in zip(tail[DATE], tail[VALUE])]


def metric_level_change(long_df: pd.DataFrame, sid: str, target_date: str) -> tuple[float, float] | None:
    """某序列在 target_date 的电平与日变化量,供前端指标表。

    用**真实观测点**(非 ffill 宽表)的相邻两点算变化:对停更/低频序列,这是「最近一次真实
    变动」而非被前向填充成 0。缺失返回 None。
    """
    sub = long_df[(long_df["series_id"] == sid) & (long_df[DATE] <= target_date)].sort_values(DATE)
    vals = sub[VALUE].tolist()
    if not vals:
        return None
    level = float(vals[-1])
    change = float(vals[-1] - vals[-2]) if len(vals) >= 2 else 0.0
    return level, change


# ── 特征视图注册表(signals 块的单一事实源)──────────────────────────────
# 决定「哪些特征露出给前端、叫什么名、什么单位、归哪组」。值取自 snapshot_at(snap),与喂 LLM 的
# prompt 特征块同读一份 snap(故数值一致)。unit:pct=带符号%、pct0=无符号%、bp、z、corr、yield(电平%)。
# 顺序即前端分组展示顺序。缺失的键(早期历史 NaN)在 build_signals 中自动跳过。
FEATURE_VIEW: tuple[tuple[str, str, str, str], ...] = (
    # 趋势:距 200 日均线
    ("SP500_px_vs_ma200", "标普500 距MA200", "pct", "trend"),
    ("NASDAQCOM_px_vs_ma200", "纳指 距MA200", "pct", "trend"),
    ("XAUUSD_px_vs_ma200", "黄金 距MA200", "pct", "trend"),
    ("DTWEXBGS_px_vs_ma200", "广义美元 距MA200", "pct", "trend"),
    # 动量:近 20 日(价格类收益率 / 利率类 bp 变化)
    ("SP500_ret_20", "标普500 近20日", "pct", "momentum"),
    ("NASDAQCOM_ret_20", "纳指 近20日", "pct", "momentum"),
    ("XAUUSD_ret_20", "黄金 近20日", "pct", "momentum"),
    ("DGS10_chg_20", "10Y 近20日", "bp", "momentum"),
    ("DGS2_chg_20", "2Y 近20日", "bp", "momentum"),
    ("DFII10_chg_20", "实际10Y 近20日", "bp", "momentum"),
    # 波动与风险
    ("VIXCLS_z_252", "VIX z分数", "z", "vol"),
    ("SP500_vol_20", "标普 20日年化波动", "pct0", "vol"),
    ("SP500_vol_60", "标普 60日年化波动", "pct0", "vol"),
    ("SP500_maxdd_252", "标普 252日最大回撤", "pct", "vol"),
    ("XAUUSD_maxdd_252", "黄金 252日最大回撤", "pct", "vol"),
    # 利率与通胀(电平)
    ("DGS2_level", "2Y 收益率", "yield", "rates"),
    ("DGS10_level", "10Y 收益率", "yield", "rates"),
    ("T10Y2Y_level", "2s10s 利差", "yield", "rates"),
    ("DFII10_level", "10Y 实际利率", "yield", "rates"),
    ("T10YIE_level", "通胀预期", "yield", "rates"),
    # 美元
    ("DTWEXBGS_z_252", "广义美元 z分数", "z", "dollar"),
    ("usd_broad_vs_narrow_div_20", "广义vs窄口径 20日背离", "pct", "dollar"),
    # 跨资产 60 日滚动相关
    ("corr_SP500_DGS10_60", "标普~10Y", "corr", "cross_asset"),
    ("corr_SP500_VIXCLS_60", "标普~VIX", "corr", "cross_asset"),
    ("corr_XAUUSD_DFII10_60", "黄金~实际利率", "corr", "cross_asset"),
    ("corr_XAUUSD_DTWEXBGS_60", "黄金~广义美元", "corr", "cross_asset"),
    # 极值 / 位置:52 周区间分位
    ("SP500_rangepct_252", "标普500 52周分位", "pct0", "range"),
    ("NASDAQCOM_rangepct_252", "纳指 52周分位", "pct0", "range"),
    ("XAUUSD_rangepct_252", "黄金 52周分位", "pct0", "range"),
)


def macro_latest(long_df: pd.DataFrame, target_date: str) -> list[dict[str, object]]:
    """月频宏观在 target_date 前的最新读数(只作背景,不进特征/回测)。"""
    out: list[dict[str, object]] = []
    for sid in catalog.MACRO_IDS:
        sub = long_df[(long_df["series_id"] == sid) & (long_df[DATE] <= target_date)]
        if sub.empty:
            continue
        last = sub.sort_values(DATE).iloc[-1]
        out.append(
            {
                "series_id": sid,
                "label": catalog.SPEC_BY_ID[sid].label,
                "obs_date": last[DATE],
                "value": float(last[VALUE]),
            }
        )
    return out
