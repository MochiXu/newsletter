"""读取数据平面(Rust)产出的观测:data/observations.csv。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Observation:
    run_date: str
    series_id: str
    label: str
    obs_date: str
    value: float
    unit: str
    source: str
    note: str


def _to_observation(r: dict) -> Observation | None:
    """把一行 CSV dict 转成 Observation;value 非法时返回 None。"""
    try:
        value = float(r["value"])
    except (KeyError, ValueError):
        return None
    return Observation(
        run_date=r["run_date"],
        series_id=r["series_id"],
        label=r["label"],
        obs_date=r["obs_date"],
        value=value,
        unit=r["unit"],
        source=r["source"],
        note=r.get("note", ""),
    )


def load_all(csv_path: Path) -> list[Observation]:
    """返回 CSV 里的全部观测(按文件顺序,跨 run_date)。文件缺失/为空时返回 []。

    用于跨日计算(如指标相邻交易日的变化量);单日视图用 load_latest。
    """
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        return [o for o in (_to_observation(r) for r in csv.DictReader(f)) if o is not None]


def load_latest(csv_path: Path) -> list[Observation]:
    """返回最新一个 run_date 的全部观测(按文件顺序)。文件缺失/为空时返回 []。"""
    rows = load_all(csv_path)
    if not rows:
        return []
    latest = max(o.run_date for o in rows)
    return [o for o in rows if o.run_date == latest]
