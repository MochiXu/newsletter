"""量化因子层(v1.6 S1)——`snap` 的高阶聚合,产出可解释的因子打分 + 代码基线 + 波动率预测。

定位(见 docs/refactor/v1.6-progress.md §2):
- **纯函数,`snap` 的高阶变换**:`snap` 已是因果快照(features.snapshot_at)→ 因子天然因果,无需另算窗口。
- **三个用途**:① 喂 LLM 当锚(prompt 因子段);② 落 briefs.json 的 `factors` 块给前端;
  ③ **自产一个代码基线方向/信心**(baseline_dir/conf),当 AI 的"陪练标尺"——评估层(S3)拿它当基线之一。
- **不追求方向预测准**(方向本就难预测):因子层的价值在 grounding + 提供高质量基线 + 波动率(唯一真能预测的量)。

合成只用**有方向含义**的因子(趋势 + 动量为主,价值给小的均值回归反向权重);波动/regime 作上下文不进方向合成。
权重为初值、宜少宜稳,后按 S3 校准结果回调——**不做花哨优化**(避免过拟合)。
"""

from __future__ import annotations

from dataclasses import dataclass

from . import catalog

# ── 合成参数(初值;后按校准回调)────────────────────────────────────────
_W_TREND = 0.5
_W_MOM = 0.4
_W_VALUE = 0.1  # 价值仅在极端时计入(均值回归),权重小
_DEADZONE = 0.1  # |composite| < 此值 → flat(无方向)
_VALUE_EXTREME = 0.6  # |value| 超过才认为"贵/便宜到值得反向"

# 各因子的归一化标度(把原始特征压到约 [-1,1])
_TREND_SCALE = 0.10  # 距 MA200 ±10% → ±1
_MOM_SCALE = 0.10  # 近 20 日收益 ±10% → ±1
_RATE_TREND_BP = 50.0  # 利率 60 日 ±50bp → ±1
_RATE_MOM_BP = 30.0  # 利率 20 日 ±30bp → ±1
_RATE_VALUE_Z = 2.0  # 利率 z 分数 ±2σ → ±1


@dataclass(frozen=True)
class AssetFactors:
    """单资产的因子视图:归一化打分 + 合成方向 + 代码基线信心 + 波动率预测。"""

    scores: dict[str, float]  # trend / momentum / value(各约 [-1,1])
    composite: float  # 方向合成分(约 [-1,1])
    baseline_dir: str  # up / down / flat
    baseline_conf: float  # 0.5~0.95,由 |composite| 单调映射(未校准)
    vol_forecast_ann: float  # EWMA 年化波动预测(价格/指数才有;利率为 0)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _get(snap: dict[str, float], key: str, default: float = 0.0) -> float:
    """取特征,缺失(早期历史 NaN 被丢)→ 默认值。"""
    v = snap.get(key)
    return float(v) if v is not None else default


def _price_factors(sid: str, snap: dict[str, float]) -> tuple[float, float, float, float | None]:
    """价格/指数:趋势=距MA200、动量=近20日收益、价值=52周分位(高=贵)、vol=EWMA 波动预测。"""
    trend = _clip(_get(snap, f"{sid}_px_vs_ma200") / _TREND_SCALE)
    mom = _clip(_get(snap, f"{sid}_ret_20") / _MOM_SCALE)
    rp = snap.get(f"{sid}_rangepct_252")
    value = _clip((float(rp) - 0.5) * 2.0) if rp is not None else 0.0  # 高分位=贵→均值回归看跌
    vol = snap.get(f"{sid}_vol_ewma")
    return trend, mom, value, (float(vol) if vol is not None else None)


def _rate_factors(sid: str, snap: dict[str, float]) -> tuple[float, float, float, float | None]:
    """利率(无 px_vs_ma200/ret/rangepct):趋势=60日bp变化、动量=20日bp变化、价值=电平 z 分数。"""
    trend = _clip(_get(snap, f"{sid}_chg_60") / _RATE_TREND_BP)
    mom = _clip(_get(snap, f"{sid}_chg_20") / _RATE_MOM_BP)
    value = _clip(_get(snap, f"{sid}_z_{_zkey()}") / _RATE_VALUE_Z)
    return trend, mom, value, None  # 利率暂不出波动预测(features 只给价格/指数算 EWMA)


def _zkey() -> str:
    from .config import WINDOWS

    return str(WINDOWS.zscore)


def _compose(trend: float, mom: float, value: float) -> tuple[float, str, float]:
    """方向合成 + 基线方向 + 基线信心。价值仅在极端时反向计入(均值回归)。"""
    value_extreme = value if abs(value) > _VALUE_EXTREME else 0.0
    composite = _clip(_W_TREND * trend + _W_MOM * mom - _W_VALUE * value_extreme)
    if composite > _DEADZONE:
        direction = "up"
    elif composite < -_DEADZONE:
        direction = "down"
    else:
        direction = "flat"
    conf = 0.5 + min(0.45, 0.5 * abs(composite))  # |composite|→[0.5,0.95];未校准,交 S3 评估
    return composite, direction, conf


def compute_factors(snap: dict[str, float]) -> dict[str, AssetFactors]:
    """对固定 roster 各资产算因子视图。key = series_id(大写,catalog 口径)。"""
    out: dict[str, AssetFactors] = {}
    for sid in catalog.PREDICTION_TARGET_IDS:
        spec = catalog.SPEC_BY_ID.get(sid)
        if spec is None:
            continue
        if spec.kind in (catalog.KIND_RATE, catalog.KIND_SPREAD):
            trend, mom, value, vol = _rate_factors(sid, snap)
        else:
            trend, mom, value, vol = _price_factors(sid, snap)
        composite, direction, conf = _compose(trend, mom, value)
        scores = {"trend": round(trend, 4), "momentum": round(mom, 4), "value": round(value, 4)}
        out[sid] = AssetFactors(
            scores=scores,
            composite=round(composite, 4),
            baseline_dir=direction,
            baseline_conf=round(conf, 4),
            vol_forecast_ann=round(float(vol), 4) if vol is not None else 0.0,
        )
    return out
