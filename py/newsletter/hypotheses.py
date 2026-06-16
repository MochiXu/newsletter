"""假设追踪日志(trust/learning engine)—— M2。

把每日简报产出的「可证伪假设」记进 `data/hypotheses.csv`,次日起用 LLM 对照最新数据
复盘:held(兑现)/ invalidated(失效)/ open(待观察)。几乎没人做这件事——它既是信任
引擎,也是作者复盘学习的核心。

纯标准库(csv);LLM 复盘复用 providers 的 `call_structured`。
"""

from __future__ import annotations

import csv
from pathlib import Path

from .providers import select_provider

FIELDS = ["created_date", "if_then", "invalidation", "status", "resolved_date", "verdict", "note"]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def open_items(rows: list[dict]) -> list[dict]:
    return [r for r in rows if (r.get("status") or "open") == "open"]


def record_new(rows: list[dict], run_date: str, hypotheses: list[dict] | None) -> list[dict]:
    """把今天简报里的新假设加入日志(按 created_date+if_then 去重)。"""
    existing = {(r.get("created_date"), r.get("if_then")) for r in rows}
    for h in hypotheses or []:
        if not isinstance(h, dict):  # LLM 偶尔返回字符串/非对象,跳过防止崩溃
            continue
        if_then = (h.get("if_then") or "").strip()
        if not if_then or (run_date, if_then) in existing:
            continue
        rows.append(
            {
                "created_date": run_date,
                "if_then": if_then,
                "invalidation": h.get("invalidation", ""),
                "status": "open",
                "resolved_date": "",
                "verdict": "",
                "note": "",
            }
        )
        existing.add((run_date, if_then))
    return rows


def apply_reviews(open_hyps: list[dict], reviews: list[dict] | None, run_date: str) -> None:
    """把 LLM 复盘结论按 index(1-based,对应传入的 open_hyps 顺序)原地写回。

    用序号而非 if_then 原文对齐——避免 LLM 改写措辞导致匹配不上。
    open_hyps 是 hyp_rows 里 open 项的引用,更新它即更新日志。
    """
    for rv in reviews or []:
        idx = rv.get("index")
        if not isinstance(idx, int) or not (1 <= idx <= len(open_hyps)):
            continue
        r = open_hyps[idx - 1]
        r["note"] = rv.get("note", r.get("note", ""))
        if rv.get("status") in ("held", "invalidated"):
            r["status"] = rv["status"]
            r["verdict"] = rv["status"]
            r["resolved_date"] = run_date


# ── LLM 复盘 ──────────────────────────────────────────────────────────

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "对应列表里的序号(从 1 起)"},
                    "status": {
                        "type": "string",
                        "enum": ["held", "invalidated", "open"],
                        "description": "held=已兑现/成立;invalidated=失效条件已触发;open=尚无定论",
                    },
                    "note": {"type": "string", "description": "依据今日数据的简短判断"},
                },
                "required": ["index", "status", "note"],
            },
        }
    },
    "required": ["reviews"],
}

REVIEW_SYSTEM = (
    "你是假设复盘助手。给你一批此前的可证伪假设(含失效条件)与今天的最新宏观数据,"
    "逐条判断:held(已成立/兑现)、invalidated(失效条件已触发)、open(尚无定论)。"
    "只依据给定数据,给出简短依据;绝不给买/卖建议。"
)


def review(open_hyps: list[dict], data_block: str) -> list[dict] | None:
    """对 open 假设逐条复盘;无 provider 或无 open 假设时返回 None。"""
    provider = select_provider()
    if provider is None or not open_hyps:
        return None
    listing = "\n".join(
        f"{i + 1}. 假设:{h.get('if_then', '')};失效条件:{h.get('invalidation', '')}"
        for i, h in enumerate(open_hyps)
    )
    user = (
        "## 今日数据\n" + data_block + "\n\n## 待复盘假设\n" + listing
        + "\n\n请逐条判断 held/invalidated/open,用列表序号 index 对齐并给出简短依据。"
    )
    result = provider.call_structured(
        REVIEW_SYSTEM, user, "review_hypotheses", "复盘此前假设是否成立", REVIEW_SCHEMA
    )
    return result.get("reviews")
