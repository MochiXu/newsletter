"""代码派生的 regime 标签。

从特征快照里用确定性规则打出分类标签(趋势/波动/曲线/实际利率/美元),省得让 LLM 去
「猜」这些本可由代码判定的状态,也为 v2 评估层埋点。全部对缺失输入健壮(缺则跳过该标签)。
"""

from __future__ import annotations


def _trend_ma200(feat: dict, sid: str) -> str | None:
    flag = feat.get(f"{sid}_above_ma200")
    if flag is None:
        return None
    return "above_ma200" if flag > 0.5 else "below_ma200"


def derive(feat: dict[str, float]) -> dict[str, str]:
    """从特征快照派生 regime 标签。"""
    out: dict[str, str] = {}

    # 股市趋势
    t = _trend_ma200(feat, "SP500")
    if t:
        out["equity_trend"] = t

    # 波动率 regime:VIX 档位 + 相对 20 日均线的高/低
    vix = feat.get("VIXCLS_level")
    if vix is not None:
        level = "low" if vix < 15 else ("mid" if vix <= 20 else "high")
        ma20 = feat.get("VIXCLS_ma_20")
        bias = "" if ma20 is None else ("/elevated" if vix > ma20 else "/easing")
        out["vol_regime"] = level + bias

    # 收益率曲线:倒挂/平/正 + 走陡/走平(20 日 bp 变化)
    curve = feat.get("T10Y2Y_level")
    if curve is not None:
        shape = "inverted" if curve < 0 else ("flat" if curve <= 0.2 else "normal")
        chg = feat.get("T10Y2Y_chg_20")
        move = "" if chg is None else ("/steepening" if chg > 2 else ("/flattening" if chg < -2 else ""))
        out["curve"] = shape + move

    # 实际利率方向(20 日 bp 变化)
    rr = feat.get("DFII10_chg_20")
    if rr is not None:
        out["real_rate"] = "rising" if rr > 3 else ("falling" if rr < -3 else "flat")

    # 通胀预期方向
    be = feat.get("T10YIE_chg_20")
    if be is not None:
        out["inflation_expectations"] = "rising" if be > 3 else ("falling" if be < -3 else "flat")

    # 美元:相对长期均线的强弱 + 广义/窄口径背离
    usd = feat.get("DTWEXBGS_px_vs_ma200")
    if usd is not None:
        strength = "strong" if usd > 0 else "weak"
        div = feat.get("usd_broad_vs_narrow_div_20")
        tag = "" if div is None or abs(div) < 0.01 else "/diverging"
        out["dollar"] = strength + tag

    return out
