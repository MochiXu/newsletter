"""把简报渲染为 markdown(本地存档/飞书卡片)与纯文本(飞书文本消息)。

M2 起,简报除四层外还含「假设复盘」与「今日新闻分类」两节(均为可选参数)。
"""

from __future__ import annotations

import datetime

from .data import Observation

DISCLAIMER = "_本简报由 AI 自动生成,仅为研究框架与观察点,不构成投资建议,不承诺收益。_"


def fmt(v: float) -> str:
    """数值格式化:至多 4 位小数,去尾零。"""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _cell(s) -> str:
    """markdown 表格单元格转义:去换行、转义竖线,避免破坏表格。"""
    return str(s).replace("\n", " ").replace("\r", " ").replace("|", "\\|").strip()


def data_table(obs: list[Observation], with_note: bool = False) -> str:
    head = "| 指标 | 值 | 单位 | 观测日 | 源 |"
    sep = "|---|---:|---|---|---|"
    if with_note:
        head += " 备注 |"
        sep += "---|"
    lines = [head, sep]
    for o in obs:
        row = f"| {_cell(o.label)} | {fmt(o.value)} | {_cell(o.unit)} | {_cell(o.obs_date)} | {_cell(o.source)} |"
        if with_note:
            row += f" {_cell(o.note)} |"
        lines.append(row)
    return "\n".join(lines)


def _resolved_today(run_date, hyp_rows):
    return [
        r
        for r in hyp_rows
        if r.get("resolved_date") == run_date and (r.get("status") in ("held", "invalidated"))
    ]


def _still_open(hyp_rows):
    return [r for r in hyp_rows if (r.get("status") or "open") == "open"]


_HYP_ICON = {"held": "✅ 已兑现", "invalidated": "❌ 已失效"}


def _hyp_section_md(run_date, hyp_rows) -> list[str]:
    if not hyp_rows:
        return []
    resolved, still_open = _resolved_today(run_date, hyp_rows), _still_open(hyp_rows)
    if not resolved and not still_open:
        return []
    out = ["## 假设复盘(昨日及以前)"]
    for r in resolved:
        line = f"- {_HYP_ICON.get(r.get('status'), r.get('status'))}({r.get('created_date', '')} 起):{r.get('if_then', '')}"
        if r.get("note"):
            line += f" — {r['note']}"
        out.append(line)
    for r in still_open:
        line = f"- ⏳ 待观察({r.get('created_date', '')} 起):{r.get('if_then', '')}"
        if r.get("note"):
            line += f" — {r['note']}"
        out.append(line)
    out.append("")
    return out


def _news_section_md(news) -> list[str]:
    if not news:
        return []
    classified = any(n.get("category") for n in news)
    out = [
        "## 今日新闻(事实 / 解读 / 影响资产)"
        if classified
        else "## 今日新闻(未分类——配置 LLM provider 后自动分类)"
    ]
    for n in news:
        if n.get("category"):
            assets = "、".join(n.get("affected_assets") or []) or "—"
            line = f"- **[{n['category']}]** {n.get('summary') or n.get('title', '')} _({n.get('source', '')})_ → 影响:{assets}"
            if n.get("note"):
                line += f" — {n['note']}"
        else:
            line = f"- {n.get('title', '')} _({n.get('source', '')})_"
        out.append(line)
    out.append("")
    return out


def render_markdown(run_date, obs, brief, news=None, hyp_rows=None) -> str:
    parts = [f"# 每日宏观简报 · {run_date}", ""]
    if brief and brief.get("headline"):
        parts += [f"**{brief['headline']}**", ""]
    parts += ["## 数据快照(事实)", data_table(obs), ""]

    if brief:
        if brief.get("facts"):
            parts += ["## 事实层"] + [f"- {x}" for x in brief["facts"]] + [""]
        if brief.get("interpretation"):
            parts += ["## 解读层(判断,非事实)"] + [f"- {x}" for x in brief["interpretation"]] + [""]
        if brief.get("hypotheses"):
            parts += ["## 假设层(可证伪)"]
            for h in brief["hypotheses"]:
                parts.append(
                    f"- **若**:{h.get('if_then', '')}  \n  **失效条件**:{h.get('invalidation', '')}"
                )
            parts.append("")
        if brief.get("impact"):
            parts += ["## 影响层(观察点,非建议)"]
            for i in brief["impact"]:
                parts.append(f"- **{i.get('asset', '')}**:{i.get('watch', '')}")
            parts.append("")
    else:
        parts += [
            "## 解读 / 假设 / 影响层",
            "> 未配置任何 LLM provider(或调用失败),本次仅产出事实层。"
            "配置 Anthropic / OpenAI / MiniMax 等任一 provider 后,将自动生成 AI 解读 / 可证伪假设 / 资产观察点。",
            "",
        ]

    parts += _hyp_section_md(run_date, hyp_rows)
    parts += _news_section_md(news)
    parts += [DISCLAIMER, ""]
    return "\n".join(parts)


# ── JSON 输出(展示平面契约,见 docs/frontend-plane.md §3.1)─────────────────

# series_id -> (key, label, kind),即指标表的显示顺序。7 行:广义美元紧邻 DXY,
# 便于一眼看到「广义美元 vs DXY」背离(简报常以此为核心论点)。
_METRIC_SPECS = [
    ("DGS10", "us10y", "US10Y", "yield"),
    ("DGS2", "us2y", "US2Y", "yield"),
    ("T10Y2Y", "2s10s", "2s10s", "spread"),
    ("VIXCLS", "vix", "VIX", "index"),
    ("DX-Y.NYB", "dxy", "DXY", "index"),
    ("DTWEXBGS", "usdbroad", "广义美元", "index"),
    ("GC=F", "gold", "GOLD", "price"),
]

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 新闻分类:后端中文枚举 -> 前端英文枚举(types.ts 用英文,渲染时再映回中文)。
_CAT_EN = {"事实": "fact", "解读": "read", "事实+解读": "both", "噪音": "noise"}


def _weekday_cn(date_str: str) -> str:
    try:
        y, m, d = (int(x) for x in date_str.split("-"))
        return _WEEKDAYS[datetime.date(y, m, d).weekday()]
    except (ValueError, TypeError):
        return ""


def _series_changes(history: list[Observation]) -> dict:
    """各 series 最近两个 run_date 的值差(latest - prev);不足两期则记 0.0。

    注意:基于 run_date 相邻而非 obs_date——若上游数据停更(obs_date 未动),变化量会是
    0.0(界面表现为持平/平线),这是有意的「无新值」语义,不是错误。
    """
    by_series: dict = {}
    for o in history:
        by_series.setdefault(o.series_id, []).append(o)
    out: dict = {}
    for sid, lst in by_series.items():
        lst.sort(key=lambda o: o.run_date)
        out[sid] = round(lst[-1].value - lst[-2].value, 4) if len(lst) >= 2 else 0.0
    return out


def _metrics_json(obs: list[Observation], changes: dict) -> list[dict]:
    by_id = {o.series_id: o for o in obs}
    rows = []
    for sid, key, label, kind in _METRIC_SPECS:
        o = by_id.get(sid)
        if o is None:  # 某序列当日缺失(如降级到 Yahoo 指数)则跳过,表格行数自适应
            continue
        rows.append(
            {"key": key, "label": label, "value": o.value, "change": changes.get(sid, 0.0), "kind": kind}
        )
    return rows


def _news_json(news) -> list[dict]:
    out = []
    for n in news or []:
        cat = _CAT_EN.get(n.get("category")) if n.get("category") else None
        out.append(
            {
                "title": n.get("title", ""),
                "source": n.get("source", ""),
                "cat": cat,  # 未分类(无 LLM)时为 None,前端按「无徽章」渲染
                "assets": n.get("affected_assets") or [],
                "dir": n.get("direction") or "watch",
                "link": n.get("link", ""),
            }
        )
    return out


def _reviews_json(run_date, hyp_rows) -> list[dict]:
    out = []
    for r in _resolved_today(run_date, hyp_rows):
        out.append({"ifThen": r.get("if_then", ""), "status": r.get("status", "open"), "note": r.get("note", "")})
    for r in _still_open(hyp_rows):
        out.append({"ifThen": r.get("if_then", ""), "status": "open", "note": r.get("note", "")})
    return out


def render_json(run_date, obs, history, brief, news=None, hyp_rows=None, issue=0) -> dict:
    """组装单日结构化简报(展示平面契约)。

    - obs:当日最新观测(load_latest);history:全量观测(load_all),仅用于算变化量。
    - brief 为 None(无 LLM provider)时,四层留空数组、tone 退为 neutral——前端按空态渲染。
    - issue 由聚合层按年代序回填(此处占位,见 brief.py)。
    """
    b = brief or {}
    changes = _series_changes(history or obs)
    hyps = [
        {"ifThen": h.get("if_then", ""), "invalidation": h.get("invalidation", "")}
        for h in (b.get("hypotheses") or [])
        if isinstance(h, dict)
    ]
    impacts = [
        {"asset": i.get("asset", ""), "watch": i.get("watch", ""), "dir": i.get("direction") or "watch"}
        for i in (b.get("impact") or [])
        if isinstance(i, dict)
    ]
    return {
        "date": run_date,
        "weekday": _weekday_cn(run_date),
        "issue": issue,
        "time": "07:00 CST",
        "tone": b.get("tone") or "neutral",
        "headline": b.get("headline") or "",
        "metrics": _metrics_json(obs, changes),
        "facts": b.get("facts") or [],
        "reads": b.get("interpretation") or [],
        "hypotheses": hyps,
        "impacts": impacts,
        "reviews": _reviews_json(run_date, hyp_rows or []),
        "news": _news_json(news),
    }


def render_text(run_date, obs, brief, news=None, hyp_rows=None) -> str:
    """飞书纯文本版本(无 markdown 渲染)。"""
    lines = [f"【每日宏观简报 · {run_date}】"]
    if brief and brief.get("headline"):
        lines.append(brief["headline"])
    lines.append("— 数据 —")
    for o in obs:
        lines.append(f"{o.label}: {fmt(o.value)}{o.unit}({o.obs_date}/{o.source})")
    if brief:
        if brief.get("interpretation"):
            lines.append("— 解读 —")
            lines += [f"· {x}" for x in brief["interpretation"]]
        if brief.get("hypotheses"):
            lines.append("— 可证伪假设 —")
            for h in brief["hypotheses"]:
                lines.append(f"· 若 {h.get('if_then', '')};失效:{h.get('invalidation', '')}")
        if brief.get("impact"):
            lines.append("— 观察点(非建议)—")
            for i in brief["impact"]:
                lines.append(f"· {i.get('asset', '')}: {i.get('watch', '')}")
    else:
        lines.append("(未配置 LLM provider,仅事实层)")

    if hyp_rows:
        resolved, still_open = _resolved_today(run_date, hyp_rows), _still_open(hyp_rows)
        if resolved or still_open:
            lines.append("— 假设复盘 —")
            for r in resolved[:5]:
                lines.append(f"· {_HYP_ICON.get(r.get('status'), '')} {r.get('if_then', '')}")
            for r in still_open[:5]:
                lines.append(f"· ⏳ {r.get('if_then', '')}")

    if news:
        lines.append("— 今日新闻 —")
        for n in news[:5]:
            tag = f"[{n['category']}] " if n.get("category") else ""
            lines.append(f"· {tag}{n.get('summary') or n.get('title', '')}")

    lines.append("仅研究参考,不构成投资建议。")
    return "\n".join(lines)
