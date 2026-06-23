"""新闻本地缓存(v1.6 S5):抽取正文按 key 落盘,重跑/回填不重抓(护配额 + 礼貌 + 可复现)。

key = 文章 uuid(TheNewsAPI)或 url 的哈希(RSS)。存为 data/news_cache/extracted/<key>.txt。
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _safe_key(key: str) -> str:
    """uuid 直接用(已是安全 id);否则(url 等)取 sha1 短哈希做文件名。"""
    if key and all(c.isalnum() or c in "-_" for c in key) and len(key) <= 80:
        return key
    return hashlib.sha1((key or "").encode("utf-8")).hexdigest()[:24]


class ExtractCache:
    """抽取正文的磁盘缓存。dir 不存在则首次写时创建;读未命中返回 None。"""

    def __init__(self, root: Path):
        self.dir = root / "extracted"

    def _path(self, key: str) -> Path:
        return self.dir / f"{_safe_key(key)}.txt"

    def get(self, key: str) -> str | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None

    def put(self, key: str, text: str) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(text or "", encoding="utf-8")
        except OSError as e:
            log.debug("news cache put failed (%s): %s", key, e)
