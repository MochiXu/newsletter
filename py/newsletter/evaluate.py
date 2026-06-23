"""评估层(v1.6 S3)——前向、轻量、纯代码。

读 `predictions.csv` 的 settled 行,回答三件事(都带样本量 n,n 小不下结论):
1. **技能 skill** = 模型命中率 − max(漂移 / 动量 / 因子基线)。只有正技能才叫有预测价值。
2. **信心校准**:按桶看「自报信心 vs 实际命中频率」(报 0.7 的那批是否真有七成命中)。
3. **Brier**:信心与 0/1 结果的均方误差(+ climatology 基线对照)。

因子模型(base_dir/base_conf)当一个「参赛选手」`_factor` 同样打分(它自己不拿因子当基线)。

**严格前向**:只用真实积累的 predictions.csv(回填有发布滞后/记忆污染);bootstrap 显著性 / 多年 / 前端整页留 V2。
"""

from __future__ import annotations

import json
from pathlib import Path

from .predictions import HORIZON_DAYS, classify_move
from .sources.base import DATE, VALUE

# 信心分桶(数据少 → 粗桶;闭开区间 [lo, hi);末桶 hi=1.01 收 1.0)
BUCKETS: tuple[tuple[float, float], ...] = ((0.0, 0.6), (0.6, 0.75), (0.75, 1.01))


# ── 小工具 ──────────────────────────────────────────────────────────────
def _hit(direction: str, realized: str) -> int:
    return 1 if direction and realized and direction == realized else 0


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _round(x, d: int = 4):
    return round(x, d) if isinstance(x, (int, float)) else None


def _conf(r: dict) -> float | None:
    v = r.get("confidence")
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _modal_rate(realized: list[str]) -> float | None:
    """漂移基线命中率 = 永远预测「多数方向」的命中率 = 最频方向的占比。"""
    if not realized:
        return None
    counts: dict[str, int] = {}
    for d in realized:
        counts[d] = counts.get(d, 0) + 1
    return max(counts.values()) / len(realized)


def _trailing_dir(long_df, asset: str, created_date: str, n: int) -> str | None:
    """动量基线:created_date 往回 n 个交易日的真实走势方向(趋势延续 → 预测同向)。"""
    if long_df is None or not n:
        return None
    sub = long_df[long_df["series_id"] == asset].sort_values(DATE)
    dates = [str(d) for d in sub[DATE].tolist()]
    vals = [float(v) for v in sub[VALUE].tolist()]
    base_i = -1
    for i, d in enumerate(dates):
        if d <= created_date:
            base_i = i
        else:
            break
    prev_i = base_i - n
    if base_i < 0 or prev_i < 0:
        return None
    return classify_move(asset, vals[prev_i], vals[base_i])[0]


def _brier(rows: list[dict]) -> tuple[float | None, float | None]:
    """Brier = mean((信心 − 命中)²);基线 = climatology(用该组命中率当恒定概率)。"""
    pairs = [(c, _hit(r["direction"], r["realized_dir"])) for r in rows if (c := _conf(r)) is not None]
    if not pairs:
        return None, None
    brier = _mean([(c - h) ** 2 for c, h in pairs])
    p = _mean([h for _, h in pairs])
    base = _mean([(p - h) ** 2 for _, h in pairs])
    return brier, base


# ── 单元格(资产 × 期限)────────────────────────────────────────────────
def _cell(rows: list[dict], long_df, n_days: int, include_factor: bool) -> dict:
    hit = _mean([_hit(r["direction"], r["realized_dir"]) for r in rows])
    drift = _modal_rate([r["realized_dir"] for r in rows])
    mom = _mean([
        1 if td == r["realized_dir"] else 0
        for r in rows
        if (td := _trailing_dir(long_df, r["asset"], r["created_date"], n_days)) is not None
    ])
    factor = None
    if include_factor:
        factor = _mean([1 if r.get("base_dir") == r["realized_dir"] else 0 for r in rows if r.get("base_dir")])
    baselines = [b for b in (drift, mom, factor) if b is not None]
    skill = (hit - max(baselines)) if (hit is not None and baselines) else None
    br, brb = _brier(rows)
    return {
        "n": len(rows), "hit": _round(hit),
        "driftBaseline": _round(drift), "momentumBaseline": _round(mom), "factorBaseline": _round(factor),
        "skill": _round(skill), "brier": _round(br), "brierBaseline": _round(brb),
    }


def _calibration(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for lo, hi in BUCKETS:
        b = [r for r in rows if (c := _conf(r)) is not None and lo <= c < hi]
        if not b:
            out.append({"lo": lo, "hi": hi, "n": 0, "stated": None, "realized": None})
            continue
        out.append({
            "lo": lo, "hi": hi, "n": len(b),
            "stated": _round(_mean([_conf(r) for r in b])),
            "realized": _round(_mean([_hit(r["direction"], r["realized_dir"]) for r in b])),
        })
    return out


def _score_model(rows: list[dict], long_df, include_factor: bool) -> dict:
    by_asset: dict[str, dict] = {}
    for a in sorted({r["asset"] for r in rows}):
        arows = [r for r in rows if r["asset"] == a]
        hz: dict[str, dict] = {}
        for h in sorted({r["horizon"] for r in arows}):
            hrows = [r for r in arows if r["horizon"] == h]
            hz[h] = _cell(hrows, long_df, HORIZON_DAYS.get(h, 0), include_factor)
        by_asset[a] = hz
    o_br, o_brb = _brier(rows)
    return {
        "n": len(rows),
        "overall": {
            "n": len(rows),
            "hit": _round(_mean([_hit(r["direction"], r["realized_dir"]) for r in rows])),
            "brier": _round(o_br), "brierBaseline": _round(o_brb),
        },
        "byAsset": by_asset,
        "calibration": _calibration(rows),
    }


def _factor_rows(settled: list[dict]) -> list[dict]:
    """从 settled 行抽出因子基线作 `_factor` 选手(模型无关 → 按 (date,asset,horizon) 去重)。"""
    seen: dict[tuple, dict] = {}
    for r in settled:
        if not r.get("base_dir"):
            continue
        k = (r["created_date"], r["asset"], r["horizon"])
        if k in seen:
            continue
        seen[k] = {
            "created_date": r["created_date"], "model": "_factor", "asset": r["asset"],
            "horizon": r["horizon"], "direction": r["base_dir"], "confidence": r.get("base_conf") or "",
            "realized_dir": r["realized_dir"],
        }
    return list(seen.values())


def _lane(r: dict) -> str:
    """参赛单元 = 模型 + A/B 臂(无臂则只用模型)。A/B 对比即比 'x·A' vs 'x·B'。"""
    arm = r.get("arm") or ""
    return f"{r['model']}·{arm}" if arm else r["model"]


def score(rows: list[dict], long_df=None, as_of: str | None = None) -> dict:
    """对 settled 预测打分 → scorecard 字典。source 诚实标注(forward/backfill/mixed)。"""
    settled = [r for r in rows if (r.get("status") == "settled") and r.get("realized_dir")]
    models: dict[str, dict] = {}
    for lane in sorted({_lane(r) for r in settled}):
        models[lane] = _score_model([r for r in settled if _lane(r) == lane], long_df, include_factor=True)
    frows = _factor_rows(settled)
    if frows:
        models["_factor"] = _score_model(frows, long_df, include_factor=False)  # 不拿自己当基线
    if as_of is None:
        dates = [r.get("resolved_date") or r.get("created_date") or "" for r in settled]
        as_of = max(dates) if dates else ""
    srcs = {(r.get("source") or "forward") for r in settled}
    source = next(iter(srcs)) if len(srcs) == 1 else ("mixed" if srcs else "forward")
    return {
        "asOf": as_of, "source": source,
        "buckets": [[lo, hi] for lo, hi in BUCKETS],
        "models": models,
    }


# ── 人读 markdown ───────────────────────────────────────────────────────
def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def _signpct(x) -> str:
    return "—" if x is None else f"{x * 100:+.0f}%"


def _render_md(sc: dict) -> str:
    p: list[str] = [
        "# 预测评估 scorecard(前向)",
        f"_截至 {sc.get('asOf') or '—'};source={sc.get('source')};样本薄时 n 小,先当观察、不下结论_",
        "",
    ]
    if not sc.get("models"):
        p += ["> 暂无已结算预测(predictions.csv 无 settled 行)。", ""]
    for m, md in sc.get("models", {}).items():
        ov = md["overall"]
        p.append(f"## {m}(n={ov['n']})")
        p.append(f"- 总体命中 {_pct(ov['hit'])} · Brier {ov['brier']}(climatology 基线 {ov['brierBaseline']})")
        p.append("- 校准:" + "; ".join(
            f"[{b['lo']}-{b['hi']}) 报{_pct(b['stated'])}→实际{_pct(b['realized'])}(n{b['n']})" for b in md["calibration"]
        ))
        p.append("- 技能(命中 − 最强基线):")
        for a, hz in md["byAsset"].items():
            for h, c in hz.items():
                p.append(
                    f"  - {a} {h}:命中 {_pct(c['hit'])} vs 基线[漂移{_pct(c['driftBaseline'])}/"
                    f"动量{_pct(c['momentumBaseline'])}/因子{_pct(c['factorBaseline'])}] → 技能 {_signpct(c['skill'])}(n{c['n']})"
                )
        p.append("")
    return "\n".join(p)


def write_scorecard(rows: list[dict], long_df=None, paths=None, as_of: str | None = None) -> dict:
    """打分 + 落 data/scorecard.json(前端未来读)+ data/scorecard.md(人读)。返回 scorecard 字典。"""
    if paths is None:
        from .config import PATHS

        paths = PATHS
    sc = score(rows, long_df, as_of)
    paths.scorecard_json.parent.mkdir(parents=True, exist_ok=True)
    paths.scorecard_json.write_text(json.dumps(sc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths.scorecard_md.write_text(_render_md(sc), encoding="utf-8")
    return sc
