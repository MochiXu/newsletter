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


_FACTOR_CN = {"NASDAQCOM": "纳指", "XAUUSD": "黄金", "DTWEXBGS": "广义美元", "DGS2": "2Y"}
_FACTOR_DIR = {"up": "↑", "down": "↓", "flat": "→"}


def build_feature_block(
    target_date: str,
    metrics: list[dict[str, Any]],
    snap: dict[str, float],
    regime: dict[str, str],
    macro: list[dict[str, Any]],
    factors: dict[str, Any] | None = None,
    news_features: dict[str, Any] | None = None,
) -> str:
    """组装特征块。所有数字均来自代码计算;缺失项以 — 占位或略过。

    factors = factors.compute_factors(snap)(AssetFactors by series_id);非空则附「因子打分」段当锚。
    news_features = news.compute_news_features(...);非空则附「新闻信号」段(**仅 A/B 的 B 臂传入**)。
    """
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

    # 2b) 二阶 / 轨迹(v1.7:动量在加速/熄火、趋势斜率、波动比、FIP 连续度;均代码算)
    so_lines: list[str] = []
    for sid, name in (("NASDAQCOM", "纳指"), ("XAUUSD", "黄金"), ("DTWEXBGS", "广义美元")):
        mc, sl, vr, fp = g(f"{sid}_mom_chg_20"), g(f"{sid}_trend_slope_20"), g(f"{sid}_vol_ratio_20_60"), g(f"{sid}_fip_60")
        if mc is None and sl is None and fp is None:
            continue
        parts: list[str] = []
        if mc is not None:
            parts.append(f"动量变化 {_pct(mc)}({'加速' if mc > 0 else '熄火'})")
        if sl is not None:
            parts.append(f"趋势斜率 {_f(sl, 4)}")
        if vr is not None:
            parts.append(f"波动比 {_f(vr)}")
        if fp is not None:
            parts.append(f"连续度 {_f(fp)}")
        so_lines.append(f"- {name}:" + ";".join(parts))
    if so_lines:
        out.append("\n### 二阶 / 轨迹(动量加速度 · 趋势斜率 · 波动比 · FIP 连续度;连续度<0=连续动量易延续,>0=跳跃式易反转)")
        out.extend(so_lines)

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

    # 6.5) 因子打分(代码合成,供参考,勿自行心算)
    if factors:
        out.append("\n### 因子打分(代码合成,供参考;composite 为方向合成,正=偏多)")
        for sid, af in factors.items():
            sc = af.scores
            parts = [
                f"综合 {af.composite:+.2f}{_FACTOR_DIR.get(af.baseline_dir, '')}(代码信心 {af.baseline_conf:.0%})",
                f"趋势 {sc.get('trend', 0.0):+.2f}",
                f"动量 {sc.get('momentum', 0.0):+.2f}",
                f"价值 {sc.get('value', 0.0):+.2f}",
            ]
            if af.vol_forecast_ann:
                parts.append(f"波动预测 {af.vol_forecast_ann * 100:.0f}%")
            out.append(f"- {_FACTOR_CN.get(sid, sid)}:" + ";".join(parts))

    # 7) regime(代码判定)
    if regime:
        out.append("\n### regime(代码判定)")
        out.append("- " + ";".join(f"{k}={v}" for k, v in regime.items()))

    # 8) 月频宏观背景
    if macro:
        out.append("\n### 月频宏观(最新读数,仅背景)")
        out.append("- " + ";".join(f"{m['label']} {m['value']}({m['obs_date']})" for m in macro))

    # 9) 新闻信号(仅 B 臂;代码聚合,非裸情绪散文。v1.8:截面 + 滚动时序 + EPU/GPR/鹰鸽)
    if news_features and news_features.get("total"):
        out.append("\n### 新闻信号(代码聚合,供参考;新闻方向力弱[反身性]→ 主用于事件/不确定性/背离,勿据此过度自信)")
        ev = [k for k, v in (news_features.get("events") or {}).items() if v]
        if ev:
            out.append("- 今日事件类型:" + "、".join(ev))
        # 全局:政策不确定性 / 地缘 / 鹰鸽语调(代码算)
        glob: list[str] = []
        if news_features.get("epu") is not None:
            glob.append(f"政策不确定 EPU {news_features['epu']:.2f}")
        if news_features.get("gpr") is not None:
            glob.append(f"地缘 GPR {news_features['gpr']:.1f}")
        if news_features.get("hawkishDovish") is not None:
            hd = news_features["hawkishDovish"]
            glob.append(f"鹰鸽 {hd:+.2f}({'偏鹰' if hd > 0 else '偏鸽'})")
        if glob:
            out.append("- 全局:" + " · ".join(glob))
        trends = news_features.get("trends") or {}
        for sid, nf in (news_features.get("byAsset") or {}).items():
            head = nf.get("headlines") or []
            ns = nf.get("netSentiment")
            line = f"- {_FACTOR_CN.get(sid, sid)}:{nf['count']} 条,净情绪 {ns:+.2f}" if ns is not None else f"- {_FACTOR_CN.get(sid, sid)}:{nf['count']} 条"
            if nf.get("sentimentDispersion") is not None:
                line += f",分歧 {nf['sentimentDispersion']:.2f}"
            tr = trends.get(sid) or {}
            if tr.get("sentMean20") is not None:
                line += f";20日情绪 {tr['sentMean20']:+.2f}"
            if tr.get("sentMomentum") is not None:
                line += f",走势 {tr['sentMomentum']:+.3f}({'转好' if tr['sentMomentum'] > 0 else '转差'})"
            if tr.get("volumeZ") is not None:
                line += f",量z {tr['volumeZ']:+.1f}"
            if tr.get("divergence") is not None:
                line += f",情绪-价格背离 {tr['divergence']:+.2f}"
            if head:
                line += f";头条「{head[0][:50]}」"
            out.append(line)

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
        "事实层 = **精选**关键客观观察 + 当日事件(别逐条复述每个收盘价——已在数据表;挑值得注意的:"
        "异动、极值、背离、跨资产关系等),每条 {tag,text} 带主题标签;"
        "解读层 = 因果/机制判断(当前 regime、特征含义),每条 {tag,text} 标注所针对主题;"
        "假设层 = 对固定的纳指/黄金/广义美元/2Y **四个资产 × {5d,20d,60d} 三个期限的网格各给一条**(共 12 条)"
        "由特征驱动的预测(每个 资产×期限 恰好一条、不重不漏;同资产不同期限可给不同方向/信心 = 期限结构;"
        "写明 direction/horizon/confidence/key_factors 与可度量失效条件,低把握给低 confidence,禁止凑数);"
        "影响层给观察点并标注 direction;另给当日 tone。"
        "若接口不支持函数调用,直接输出符合 emit_brief 参数结构的 JSON,不要包裹多余文字。"
    )
