"""预测追踪账本(track record)—— 替代旧 hypotheses.py 的主观复盘。

每日把**各模型**对固定 roster 的预测记进 `data/predictions.csv`;到 horizon 期满后:
1. **代码**算真实走势 + 命中(客观裁决,见 `backfill`)——这是卡片上「实际结果」的主显;
2. **LLM** 写一句复盘叙述(为什么命中/未中,见 `review`)——旁注。

混合模式:代码给「准 / 不准、是否命中」,LLM 只解释。纯标准库(csv);LLM 复用 providers.select_provider。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from . import catalog, features
from .llm.providers import select_provider
from .models import LLMBrief, MetricKind

FIELDS = [
    "created_date", "model", "asset", "direction", "horizon", "confidence",
    "status", "resolved_date", "realized_dir", "realized_text", "hit", "note",
    "base_dir", "base_conf",  # 创建时的因子基线方向/信心(point-in-time;评估层当基线之一)
]

# horizon 枚举 → 交易日数(与 models.Horizon 对齐)
HORIZON_DAYS: dict[str, int] = {"next_1d": 1, "h_5d": 5, "h_20d": 20, "h_60d": 60}

_FLAT_PCT = 0.5   # 价格/指数:±0.5% 内算横盘(死区,避免微涨也判"涨")
_FLAT_BP = 5.0    # 利率:±5bp 内算横盘


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


def _key(r: dict) -> tuple:
    return (r.get("created_date"), r.get("model"), r.get("asset"), r.get("horizon"))


def record(
    rows: list[dict],
    created_date: str,
    views_llm: dict[str, LLMBrief | None],
    factors: dict | None = None,
) -> list[dict]:
    """登记当天**各模型**对固定 roster 的预测(status=pending)。

    按 (created_date, model, asset, horizon) 幂等:同日重跑/重试不会重复登记。
    factors = factors.compute_factors(snap)(AssetFactors by series_id);存当时的代码基线方向/信心
    (point-in-time,模型无关 → 同资产各模型行写同值),供评估层(evaluate)当基线之一。
    """
    existing = {_key(r) for r in rows}
    for model, lb in (views_llm or {}).items():
        if lb is None:
            continue
        for h in lb.hypotheses:
            if not h.asset:
                continue
            af = (factors or {}).get(h.asset)
            row = {
                "created_date": created_date, "model": model, "asset": h.asset,
                "direction": h.direction.value, "horizon": h.horizon.value,
                "confidence": f"{h.confidence:.4f}", "status": "pending",
                "resolved_date": "", "realized_dir": "", "realized_text": "", "hit": "", "note": "",
                "base_dir": af.baseline_dir if af else "",
                "base_conf": f"{af.baseline_conf:.4f}" if af else "",
            }
            if _key(row) in existing:
                continue
            rows.append(row)
            existing.add(_key(row))
    return rows


def _is_yield(asset: str) -> bool:
    spec = catalog.SPEC_BY_ID.get(asset)
    return spec is not None and spec.metric_kind in (MetricKind.YIELD, MetricKind.SPREAD)


def classify_move(asset: str, v0: float, vh: float) -> tuple[str, str]:
    """真实走势 → (realized_dir, realized_text)。利率类按 bp 变化判向,其余按 pct 收益;带死区。"""
    if _is_yield(asset):
        d_bp = (vh - v0) * 100.0
        rdir = "up" if d_bp > _FLAT_BP else "down" if d_bp < -_FLAT_BP else "flat"
        return rdir, f"{d_bp:+.0f}bp"
    pct = (vh - v0) / v0 * 100.0 if v0 else 0.0
    rdir = "up" if pct > _FLAT_PCT else "down" if pct < -_FLAT_PCT else "flat"
    return rdir, f"{pct:+.1f}%"


def backfill(rows: list[dict], long_df, target_date: str) -> list[dict]:
    """对 pending 行:若 horizon 期满(resolved_date <= target_date)→ 代码算真实走势 + 命中。

    返回本次**新结算**的行(供 LLM 复盘)。realized 与模型无关,只看资产真实走势。
    """
    newly: list[dict] = []
    for r in rows:
        if (r.get("status") or "pending") != "pending":
            continue
        n = HORIZON_DAYS.get(r.get("horizon", ""))
        if not n:
            continue
        mv = features.realized_move(long_df, r["asset"], r["created_date"], n)
        if mv is None:
            continue  # 未来交易日不足 → 仍 pending(前端沙漏)
        resolved_date, v0, vh = mv
        if resolved_date > target_date:
            continue  # 不用超过当前可见日的数据(因果)
        rdir, text = classify_move(r["asset"], v0, vh)
        r["status"] = "settled"
        r["resolved_date"] = resolved_date
        r["realized_dir"] = rdir
        r["realized_text"] = text
        r["hit"] = "1" if rdir == r.get("direction") else "0"
        newly.append(r)
    return newly


# ── LLM 复盘叙述(混合模式的「解释」那半;代码裁决已在 backfill 给出)──────────

REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "对应列表里的序号(从 1 起)"},
                    "note": {"type": "string", "description": "一句话复盘:为什么命中/未中(只依据给定结果)"},
                },
                "required": ["index", "note"],
            },
        }
    },
    "required": ["reviews"],
}

REVIEW_SYSTEM = (
    "你是预测复盘助手。给你一批已到期的方向预测,每条含:资产、预测方向/期限、以及**代码算好的**"
    "真实走势与是否命中。请逐条用一句话说明为什么命中或未中(只依据给定结果,不重新判定对错,"
    "不给买/卖建议)。"
)

_ASSET_CN = {"NASDAQCOM": "纳指", "XAUUSD": "黄金", "DTWEXBGS": "广义美元", "DGS2": "美债2Y"}
_HZ_CN = {"next_1d": "次日", "h_5d": "5日", "h_20d": "20日", "h_60d": "60日"}
_DIR_CN = {"up": "上行", "down": "下行", "flat": "横盘"}


def review(newly: list[dict]) -> None:
    """对**本次新结算**的预测逐条让 LLM 写一句复盘叙述,原地写回 note。

    一次批量调用(按 index 对齐);无 provider 或无新结算则跳过(代码裁决仍在,优雅降级)。
    """
    provider = select_provider()
    if provider is None or not newly:
        return
    listing = "\n".join(
        f"{i + 1}. {_ASSET_CN.get(r['asset'], r['asset'])} 预测 {_DIR_CN.get(r['direction'], r['direction'])}"
        f"({_HZ_CN.get(r['horizon'], r['horizon'])}),实际 {_DIR_CN.get(r['realized_dir'], r['realized_dir'])} "
        f"{r['realized_text']},{'命中' if r.get('hit') == '1' else '未中'}"
        for i, r in enumerate(newly)
    )
    user = "## 已结算预测\n" + listing + "\n\n请逐条用一句话复盘为什么命中/未中,用列表序号 index 对齐。"
    try:
        result = provider.call_structured(
            REVIEW_SYSTEM, user, "review_predictions", "复盘已结算的方向预测", REVIEW_SCHEMA
        )
    except Exception:  # noqa: BLE001 — 复盘叙述失败不影响代码裁决
        return
    for rv in (result or {}).get("reviews") or []:
        idx = rv.get("index")
        if isinstance(idx, int) and 1 <= idx <= len(newly):
            newly[idx - 1]["note"] = rv.get("note", "")
