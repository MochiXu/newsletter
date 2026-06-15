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


def load_latest(csv_path: Path) -> list[Observation]:
    """返回最新一个 run_date 的全部观测(按文件顺序)。文件缺失/为空时返回 []。"""
    if not csv_path.exists():
        return []
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows.extend(csv.DictReader(f))
    if not rows:
        return []
    latest = max(r["run_date"] for r in rows)
    out: list[Observation] = []
    for r in rows:
        if r["run_date"] != latest:
            continue
        try:
            value = float(r["value"])
        except (KeyError, ValueError):
            continue
        out.append(
            Observation(
                run_date=r["run_date"],
                series_id=r["series_id"],
                label=r["label"],
                obs_date=r["obs_date"],
                value=value,
                unit=r["unit"],
                source=r["source"],
                note=r.get("note", ""),
            )
        )
    return out
