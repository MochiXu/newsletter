"""通用时序特征算子(v1.7 / v1.8 共享地基 · 协同计划 P0)。

同一套数学,喂不同序列:
- v1.7:价格 / 因子序列 → 二阶(加速度)、轨迹(斜率 / 形状)。
- v1.8:新闻情绪 / 量序列 → 走势、动量、异常 z、反转。

设计:全部**因果**(只用过去),对短序列 / NaN 健壮。Series 版返回对齐索引的 Series;
另给标量 `last_*` 便于在"当日快照"里取末值。不依赖除 pandas 外的东西。
"""

from __future__ import annotations

import math

import pandas as pd


def _min_periods(n: int) -> int:
    return min(max(1, n), max(2, n // 2))  # 钳到窗口大小:n=1→1(不让 min_periods>window 崩)


def rolling_mean(s: pd.Series, n: int) -> pd.Series:
    """滚动均值(min_periods = n//2,短窗也给值)。"""
    return s.rolling(n, min_periods=_min_periods(n)).mean()


def momentum(s: pd.Series, n: int) -> pd.Series:
    """n 期变化:s_t − s_{t−n}(一阶)。"""
    return s - s.shift(n)


def acceleration(s: pd.Series, n: int) -> pd.Series:
    """二阶:n 期动量本身的 n 期变化 = (s_t−s_{t−n}) − (s_{t−n}−s_{t−2n})。

    >0 = 动量在加速;<0 = 在衰竭。
    """
    m = momentum(s, n)
    return m - m.shift(n)


def roc(s: pd.Series, n: int) -> pd.Series:
    """n 期变化率(%):(s_t − s_{t−n}) / |s_{t−n}|。分母 0 → NaN。"""
    base = s.shift(n)
    return (s - base) / base.abs().replace(0.0, float("nan"))


def zscore(s: pd.Series, window: int) -> pd.Series:
    """滚动 z 分数:(s − rolling_mean) / rolling_std。std=0 → NaN。

    用"偏离自身历史"而非绝对值(异常量 / 异常情绪比绝对水平更有信息)。
    """
    mp = _min_periods(window)
    mean = s.rolling(window, min_periods=mp).mean()
    std = s.rolling(window, min_periods=mp).std()
    return (s - mean) / std.replace(0.0, float("nan"))


def slope(s: pd.Series, n: int) -> pd.Series:
    """滚动线性斜率(每步变化量,OLS over 最近 n 点)。趋势在变陡 / 走平。"""
    def _fit(window: pd.Series) -> float:
        y = window.dropna().to_numpy()
        k = len(y)
        if k < 2:
            return float("nan")
        # x = 0..k-1;闭式 OLS 斜率,避免引入 numpy.polyfit 的额外开销
        xbar = (k - 1) / 2.0
        ybar = y.mean()
        num = sum((i - xbar) * (y[i] - ybar) for i in range(k))
        den = sum((i - xbar) ** 2 for i in range(k))
        return num / den if den else float("nan")

    return s.rolling(n, min_periods=_min_periods(n)).apply(_fit, raw=False)


def reversal_flag(s: pd.Series) -> pd.Series:
    """方向反转:符号与上一期相反 → 1.0,否则 0.0(0 / NaN 视为无方向→0)。"""
    sign = s.apply(lambda x: 0 if (x is None or (isinstance(x, float) and math.isnan(x))) else (1 if x > 0 else (-1 if x < 0 else 0)))
    prev = sign.shift(1).fillna(0)  # 首期无上一期 → 0(不算反转)
    return ((sign != 0) & (prev != 0) & (sign != prev)).astype(float)


def streak(s: pd.Series) -> pd.Series:
    """连续同号长度(带符号):+k = 连涨 k 期,−k = 连跌 k 期(0 重置)。"""
    out: list[float] = []
    run = 0
    for v in s.tolist():
        cur = 0 if (v is None or (isinstance(v, float) and math.isnan(v))) else (1 if v > 0 else (-1 if v < 0 else 0))
        if cur == 0:
            run = 0
        elif run != 0 and (run > 0) == (cur > 0):
            run += cur
        else:
            run = cur
        out.append(float(run))
    return pd.Series(out, index=s.index)


def dispersion(values: list[float]) -> float | None:
    """截面离散度 = 一组值的样本标准差(跨模型 / 跨文章的"分歧度")。<2 个有效值 → None。"""
    xs = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(xs) < 2:
        return None
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


# ── 标量便捷:取序列末值(用于"当日快照")──────────────────────────────────
def _last(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else None


def last_acceleration(s: pd.Series, n: int) -> float | None:
    return _last(acceleration(s, n))


def last_slope(s: pd.Series, n: int) -> float | None:
    return _last(slope(s, n))


def last_zscore(s: pd.Series, window: int) -> float | None:
    return _last(zscore(s, window))


def last_streak(s: pd.Series) -> float | None:
    return _last(streak(s))
