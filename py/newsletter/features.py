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
