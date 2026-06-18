"""原始数据层存储:parquet。

布局(见 docs/refactor/v1-progress §3):
- `data/raw/latest/series.parquet`  当前全量快照(全历史),每日重拉覆盖。tracked。
- `data/raw/latest/manifest.json`   记 pull_date 等元信息(sidecar,保持数据帧纯净)。
- `data/raw/history/series-<pull_date>.parquet`  每日归档(point-in-time)。gitignored。
- `data/features/<date>.parquet`    报告当天特征快照(排错/审计)。gitignored。

每次落盘:先把现有 latest 按其 pull_date 归档到 history,再写新 latest。history 因此
天然积累「我们在某日看到的完整序列」——v2 回测的 point-in-time 档案。
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pandas as pd

from .config import Paths
from .sources.base import DATE, VALUE

log = logging.getLogger(__name__)

_TIDY_COLS = [DATE, "series_id", VALUE, "source"]
_SERIES_FILE = "series.parquet"
_MANIFEST = "manifest.json"


class RawStore:
    """原始序列的 parquet 读写(latest / history 归档)。"""

    def __init__(self, paths: Paths):
        self.paths = paths

    @property
    def _latest_parquet(self) -> Path:
        return self.paths.raw_latest / _SERIES_FILE

    @property
    def _latest_manifest(self) -> Path:
        return self.paths.raw_latest / _MANIFEST

    def read_latest(self) -> pd.DataFrame:
        """读当前全量快照;不存在返回空 tidy 帧。"""
        if not self._latest_parquet.exists():
            return pd.DataFrame(columns=_TIDY_COLS)
        return pd.read_parquet(self._latest_parquet)

    def latest_pull_date(self) -> str | None:
        if not self._latest_manifest.exists():
            return None
        try:
            return json.loads(self._latest_manifest.read_text(encoding="utf-8")).get("pull_date")
        except (ValueError, OSError):
            return None

    def write_snapshot(self, df: pd.DataFrame, pull_date: str) -> None:
        """归档现有 latest → history,再写新 latest(parquet + manifest)。"""
        missing = [c for c in _TIDY_COLS if c not in df.columns]
        if missing:
            raise ValueError(f"raw 帧缺列: {missing}")
        self.paths.raw_latest.mkdir(parents=True, exist_ok=True)

        prev = self.latest_pull_date()
        if prev and self._latest_parquet.exists():
            self.paths.raw_history.mkdir(parents=True, exist_ok=True)
            archive = self.paths.raw_history / f"series-{prev}.parquet"
            shutil.copy2(self._latest_parquet, archive)
            log.info("archived raw snapshot -> %s", archive.name)

        df = df[_TIDY_COLS].sort_values([DATE, "series_id"], ignore_index=True)
        df.to_parquet(self._latest_parquet, index=False)
        series = sorted(df["series_id"].unique().tolist())
        manifest = {
            "pull_date": pull_date,
            "rows": int(len(df)),
            "series": series,
            "date_min": (df[DATE].min() if not df.empty else None),
            "date_max": (df[DATE].max() if not df.empty else None),
        }
        self._latest_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        log.info("wrote latest snapshot: %s rows, %s series, pull_date=%s", len(df), len(series), pull_date)

    # ── 特征快照(排错/审计)──────────────────────────────────────────────
    def write_features(self, date: str, df: pd.DataFrame) -> None:
        self.paths.features.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.paths.features / f"{date}.parquet", index=False)

    def read_features(self, date: str) -> pd.DataFrame | None:
        p = self.paths.features / f"{date}.parquet"
        return pd.read_parquet(p) if p.exists() else None
