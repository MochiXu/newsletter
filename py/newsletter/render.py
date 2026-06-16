"""把四层简报渲染为 markdown(本地存档/飞书卡片)与纯文本(飞书文本消息)。"""

from __future__ import annotations

from .data import Observation

DISCLAIMER = "_本简报由 AI 自动生成,仅为研究框架与观察点,不构成投资建议,不承诺收益。_"


def fmt(v: float) -> str:
    """数值格式化:至多 4 位小数,去尾零。"""
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def data_table(obs: list[Observation], with_note: bool = False) -> str:
    head = "| 指标 | 值 | 单位 | 观测日 | 源 |"
    sep = "|---|---:|---|---|---|"
    if with_note:
        head += " 备注 |"
        sep += "---|"
    lines = [head, sep]
    for o in obs:
        row = f"| {o.label} | {fmt(o.value)} | {o.unit} | {o.obs_date} | {o.source} |"
        if with_note:
            row += f" {o.note} |"
        lines.append(row)
    return "\n".join(lines)


def render_markdown(run_date: str, obs: list[Observation], brief: dict | None) -> str:
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

    parts += [DISCLAIMER, ""]
    return "\n".join(parts)


def render_text(run_date: str, obs: list[Observation], brief: dict | None) -> str:
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
    lines.append("仅研究参考,不构成投资建议。")
    return "\n".join(lines)
