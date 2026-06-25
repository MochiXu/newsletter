"""新闻语料库(v1.8 P1):单一 article-level parquet,按月分区、uuid 幂等。

既是**语料**(body + 标签 + 元数据,供重处理/聚合),又是**"别重抓/别重分析"的缓存**
(抓前查 uuid)。列存 → body 同表不拖慢只读特征列的聚合。退役旧 txt `news_cache`。

设计:核心字段固定列 + `extra`(JSON 串)向后扩展;list/dict 字段一律 JSON 串存(parquet 友好、
DuckDB 可直查)。聚合(日/滚动)由 features 层从本表算,不在此落盘。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# 固定列(标准公共字段,参考 schema.org NewsArticle / GDELT 通用集)。顺序即列序。
_STR = ""
_COLUMNS: dict[str, object] = {
    # 身份 / 时间
    "uuid": _STR, "published_at": _STR, "first_seen_date": _STR,
    # 来源 / 溯源
    "source": _STR, "domain": _STR, "url": _STR, "author": _STR, "language": _STR,
    "locale": _STR, "source_tag": "forward",
    # 内容
    "title": _STR, "description": _STR, "body": _STR, "word_count": 0,
    # 逐篇分析(LLM)
    "category": _STR, "direction": _STR, "sentiment_score": float("nan"),
    "affected_assets": "[]", "entities": "[]", "keywords": "[]", "event_types": "[]",
    "summary": _STR, "quality_score": float("nan"), "relevance_score": float("nan"),
    "uncertainty_score": float("nan"), "hawkish_dovish": float("nan"),
    # 演进
    "schema_version": SCHEMA_VERSION, "extra": "{}",
}
_JSON_FIELDS = ("affected_assets", "entities", "keywords", "event_types", "extra")


def _as_json(v: object) -> str:
    """list/dict → JSON 串;已是串则原样;None → 空容器串。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""


def normalize_record(rec: dict) -> dict:
    """补全所有固定列(缺则填默认),JSON 字段序列化,丢弃未知键到 extra 之外不动。"""
    out: dict[str, object] = {}
    for col, default in _COLUMNS.items():
        out[col] = rec.get(col, default)
    for f in _JSON_FIELDS:
        out[f] = _as_json(out[f])
    out["schema_version"] = SCHEMA_VERSION
    if not out.get("first_seen_date") and out.get("published_at"):
        out["first_seen_date"] = str(out["published_at"])[:10]
    return out


def _month_of(rec: dict) -> str:
    """归月分区键 YYYY-MM:优先 published_at,退回 first_seen_date。"""
    key = str(rec.get("published_at") or rec.get("first_seen_date") or "")[:7]
    return key or "unknown"


class NewsStore:
    """article-level 语料库的月分区 parquet 读写(uuid 幂等)。"""

    def __init__(self, root: Path):
        self.dir = root

    def _path(self, ym: str) -> Path:
        return self.dir / f"news-{ym}.parquet"

    def _read_month(self, ym: str) -> pd.DataFrame:
        p = self._path(ym)
        if not p.exists():
            return pd.DataFrame(columns=list(_COLUMNS))
        try:
            return pd.read_parquet(p)
        except Exception as e:  # noqa: BLE001 — 损坏文件不阻断
            log.warning("news store 读取失败 %s: %s", p, e)
            return pd.DataFrame(columns=list(_COLUMNS))

    def existing_uuids(self, months: list[str]) -> set[str]:
        """给定月份里已存在的 uuid 集合(抓前去重用)。"""
        seen: set[str] = set()
        for ym in set(months):
            df = self._read_month(ym)
            if "uuid" in df.columns and not df.empty:
                seen.update(str(u) for u in df["uuid"].tolist())
        return seen

    def upsert(self, records: list[dict]) -> int:
        """写入/合并(按 uuid 去重,keep=last → 重分析覆盖)。返回写入条数。"""
        norm = [normalize_record(r) for r in records if r.get("uuid")]
        if not norm:
            return 0
        self.dir.mkdir(parents=True, exist_ok=True)
        by_month: dict[str, list[dict]] = {}
        for r in norm:
            by_month.setdefault(_month_of(r), []).append(r)
        written = 0
        for ym, rows in by_month.items():
            old = self._read_month(ym)
            new = pd.DataFrame(rows, columns=list(_COLUMNS))
            merged = pd.concat([old, new], ignore_index=True) if not old.empty else new
            merged = merged.drop_duplicates(subset=["uuid"], keep="last").reset_index(drop=True)
            merged.to_parquet(self._path(ym), index=False)
            written += len(rows)
        return written

    def load(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        """读取 [start, end] 内的文章(按 published_at 过滤;None=不限)。跨月合并。"""
        if not self.dir.exists():
            return pd.DataFrame(columns=list(_COLUMNS))
        frames = [self._read_month(p.stem.replace("news-", "")) for p in sorted(self.dir.glob("news-*.parquet"))]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame(columns=list(_COLUMNS))
        df = pd.concat(frames, ignore_index=True)
        if "published_at" in df.columns and (start or end):
            d = df["published_at"].astype(str).str[:10]
            mask = pd.Series(True, index=df.index)
            if start:
                mask &= d >= start
            if end:
                mask &= d <= end
            df = df[mask]
        return df.reset_index(drop=True)
