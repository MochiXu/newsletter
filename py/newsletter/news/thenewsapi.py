"""TheNewsAPI 源(v1.6 S5 主源)。

要点(实测,见 docs/news-sources.md §2):
- **Cloudflare**:必须浏览器 UA(`BROWSER_UA`),否则 403/1010。
- **多 key 轮换**:免费档 100 次/天/key × 3 条/请求;3 个 key 轮换护额度(回填 + live 都够)。
- **源白名单**:裸 search 噪音极大 → 必须用 `source_ids` 白名单(见 §5,人工筛定的财经专业源)。
- 历史很深(无 1 月硬墙);snippet/description ≈160 字 → 仍需 extract 抓全文。
"""

from __future__ import annotations

import logging
import os

from ..sources.base import FetchError, http_get_json
from .base import BROWSER_UA, NewsItem

log = logging.getLogger(__name__)

_BASE = "https://api.thenewsapi.com/v1/news/all"

# 财经专业源白名单(docs/news-sources.md §5)。**实测筛定**(2026-06,见 §6 诊断):
# - source_id 必须用 /sources 端点拿到的真实值(早期版本几乎全填错 → 全部 miss → 噪音兜底到 Benzinga)。
# - 只保留"能抓到真全文"的源:逐源拉最新 3 条实测抽取,中位本文 >2000 字、无 paywall/免责残文。
# - 剔除:Benzinga(正文 JS 墙,抽出来只有小标题 + 免责)、FT / SeekingAlpha(硬 paywall,抽 0 字)、
#   dailyfx(抽 0 字);reuters/bloomberg/wsj/marketwatch/kitco 免费档根本不在源列表里。
# - economictimes 转载 Reuters/AP/Bloomberg 通讯社全球宏观稿,正文完整,是拿"通讯社内容"的可行替身。
SOURCE_ALLOWLIST: tuple[str, ...] = (
    "cnbc.com-1", "cnbc.com-2", "cnbc.com-3",
    "finance.yahoo.com-2",
    "investing.com-18",
    "economictimes.indiatimes.com-2", "economictimes.indiatimes.com-3",
    "fortune.com-1",
    "businessinsider.com-1", "businessinsider.com-2",
    "forbes.com-1",
)


def _keys_from_env() -> list[str]:
    """`THENEWSAPI_KEYS`(逗号分隔多 key 轮换)优先,退回单 `THENEWSAPI_KEY`。"""
    multi = os.environ.get("THENEWSAPI_KEYS", "")
    keys = [k.strip() for k in multi.split(",") if k.strip()]
    if not keys:
        one = os.environ.get("THENEWSAPI_KEY", "").strip()
        if one:
            keys = [one]
    return keys


class TheNewsApiProvider:
    """TheNewsAPI /v1/news/all。按资产关键词查询、限定优质源白名单、跨 key 轮换。"""

    name = "thenewsapi"
    needs_key = True
    supports_query = True

    def __init__(self, keys: list[str] | None = None, source_ids: tuple[str, ...] = SOURCE_ALLOWLIST):
        self.keys = keys if keys is not None else _keys_from_env()
        self.source_ids = source_ids
        self._ki = 0

    def _next_key(self) -> str:
        k = self.keys[self._ki % len(self.keys)]
        self._ki += 1
        return k

    @staticmethod
    def _to_items(data: list, asset: str) -> list[NewsItem]:
        out: list[NewsItem] = []
        for a in data or []:
            if not isinstance(a, dict) or not a.get("url"):
                continue
            out.append(
                NewsItem(
                    source=a.get("source", ""),
                    title=a.get("title", ""),
                    link=a.get("url", ""),
                    published=(a.get("published_at") or "")[:19],
                    summary=a.get("description") or a.get("snippet") or "",
                    uuid=a.get("uuid", ""),
                    asset=asset,
                )
            )
        return out

    def fetch(
        self,
        query: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 3,
        asset: str = "",
    ) -> list[NewsItem]:
        """查一页新闻。free 档单页 ≤3 条;source_ids 白名单 + en + 时序排序。无 key 返回 []。"""
        if not self.keys:
            return []
        params = {
            "api_token": self._next_key(),
            "language": "en",
            "limit": min(limit, 3),  # free 档单页最多 3 条
            "sort": "published_at",
        }
        if query:
            params["search"] = query
            # 只搜标题+描述,避免正文偶然提及("豪宅里的 gold")带来的低相关噪音
            params["search_fields"] = "title,description"
        if self.source_ids:
            params["source_ids"] = ",".join(self.source_ids)
        if start:
            params["published_after"] = start
        if end:
            params["published_before"] = end
        from urllib.parse import urlencode

        url = f"{_BASE}?{urlencode(params)}"
        try:
            data = http_get_json(url, headers={"User-Agent": BROWSER_UA}, timeout=25)
        except FetchError as e:
            log.warning("thenewsapi fetch failed (asset=%s): %s", asset, e)
            return []
        return self._to_items((data or {}).get("data", []) if isinstance(data, dict) else [], asset)
