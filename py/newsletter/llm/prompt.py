"""把已算好的技术特征渲染成喂给 LLM 的「特征块」(固定格式),并组装 user 消息。

强制分层的关键:LLM 读到的是**代码算好的数字**(带白话标签与单位),而非原始值堆叠。
纯函数,便于测试与排错。
"""

from __future__ import annotations

from typing import Any


def _pct(x: float | None, signed: bool = True) -> str:
    if x is None:
        return "—"
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def _bp(x: float | None) -> str:
    return "—" if x is None else f"{x:+.0f}bp"


def _f(x: float | None, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def _level(value: float, kind: str) -> str:
    if kind in ("yield", "spread"):
        return f"{value:.2f}%"
    if kind == "price":
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def build_feature_block(
    target_date: str,
    metrics: list[dict[str, Any]],
    snap: dict[str, float],
    regime: dict[str, str],
    macro: list[dict[str, Any]],
) -> str:
    """组装特征块。所有数字均来自代码计算;缺失项以 — 占位或略过。"""
    g = snap.get
    out: list[str] = [f"## 今日数据与技术特征(截至 {target_date},均由代码计算,请勿自行心算)"]

    # 1) 电平 + 日变化
    out.append("\n### 关键电平(值 · 日变化)")
    for m in metrics:
        out.append(f"- {m['label']}:{_level(m['value'], m['kind'])} · Δ {_chg_str(m['change'], m['kind'])}")

    # 2) 趋势与动量(价格/指数)
    out.append("\n### 趋势与动量")
    for sid, name in (("SP500", "标普500"), ("NASDAQCOM", "纳指"), ("XAUUSD", "黄金")):
        r20, vma, dd, rp = g(f"{sid}_ret_20"), g(f"{sid}_px_vs_ma200"), g(f"{sid}_maxdd_252"), g(f"{sid}_rangepct_252")
        if r20 is None and vma is None:
            continue
        parts = [f"近20日 {_pct(r20)}"]
        if vma is not None:
            parts.append(f"较MA200 {_pct(vma)}({'上方' if vma > 0 else '下方'})")
        if rp is not None:
            parts.append(f"52周分位 {_pct(rp, signed=False)}")
        if dd is not None:
            parts.append(f"252日最大回撤 {_pct(dd)}")
        out.append(f"- {name}:" + ";".join(parts))

    # 3) 利率与通胀
    out.append("\n### 利率与通胀")
    out.append(
        f"- 10Y {_f(g('DGS10_level'))}%(20日 {_bp(g('DGS10_chg_20'))});"
        f"2Y {_f(g('DGS2_level'))}%(20日 {_bp(g('DGS2_chg_20'))});"
        f"2s10s {_f(g('T10Y2Y_level'))}%(20日 {_bp(g('T10Y2Y_chg_20'))})"
    )
    out.append(
        f"- 实际利率10Y {_f(g('DFII10_level'))}%(20日 {_bp(g('DFII10_chg_20'))});"
        f"通胀预期 {_f(g('T10YIE_level'))}%(20日 {_bp(g('T10YIE_chg_20'))})"
    )

    # 4) 波动与风险
    out.append("\n### 波动与风险")
    out.append(
        f"- VIX {_f(g('VIXCLS_level'))}(z={_f(g('VIXCLS_z_252'))});"
        f"标普20日年化波动 {_pct(g('SP500_vol_20'), signed=False)};"
        f"标普60日年化波动 {_pct(g('SP500_vol_60'), signed=False)}"
    )

    # 5) 美元(代理只比收益率/趋势/标准化)
    out.append("\n### 美元")
    out.append(
        f"- 广义美元:较MA200 {_pct(g('DTWEXBGS_px_vs_ma200'))}、20日 {_pct(g('DTWEXBGS_ret_20'))}、z={_f(g('DTWEXBGS_z_252'))}"
    )
    out.append(
        f"- 广义 vs 窄口径(UUP 代理)20日收益背离:{_pct(g('usd_broad_vs_narrow_div_20'))}"
        "(正=广义更强;UUP 仅作趋势/标准化代理)"
    )

    # 6) 跨资产 60 日相关
    out.append("\n### 跨资产相关(60日)")
    out.append(
        f"- 标普~10Y {_f(g('corr_SP500_DGS10_60'))};标普~VIX {_f(g('corr_SP500_VIXCLS_60'))};"
        f"黄金~实际利率 {_f(g('corr_XAUUSD_DFII10_60'))};黄金~广义美元 {_f(g('corr_XAUUSD_DTWEXBGS_60'))}"
    )

    # 7) regime(代码判定)
    if regime:
        out.append("\n### regime(代码判定)")
        out.append("- " + ";".join(f"{k}={v}" for k, v in regime.items()))

    # 8) 月频宏观背景
    if macro:
        out.append("\n### 月频宏观(最新读数,仅背景)")
        out.append("- " + ";".join(f"{m['label']} {m['value']}({m['obs_date']})" for m in macro))

    return "\n".join(out)


def _chg_str(change: float, kind: str) -> str:
    if kind in ("yield", "spread"):
        return f"{change * 100:+.0f}bp"
    return f"{change:+.2f}"


def build_user(feature_block: str, linkage_map: str) -> str:
    return (
        feature_block
        + "\n\n## 宏观传导图(你的推理依据)\n"
        + linkage_map
        + "\n\n请基于以上**已算好的特征**,通过 emit_brief 输出四层简报:"
        "事实层复述关键特征;解读层标注为判断(当前 regime、特征含义);"
        "假设层 = 对固定的纳指/黄金/广义美元/2Y 四个方向**各给且只给一条由特征驱动的预测**"
        "(写明 direction/horizon/confidence/key_factors 与可度量失效条件,低把握给低 confidence,禁止凑数);"
        "影响层给观察点并标注 direction;另给当日 tone。"
        "若接口不支持函数调用,直接输出符合 emit_brief 参数结构的 JSON,不要包裹多余文字。"
    )
