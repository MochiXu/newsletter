"""把简报渲染为 markdown(本地存档/飞书卡片)与纯文本(飞书文本消息)。

M2 起,简报除四层外还含「假设复盘」与「今日新闻分类」两节(均为可选参数)。
"""

from __future__ import annotations

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
