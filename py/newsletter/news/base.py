"""新闻多接口的统一契约(v1.6 S5)。

- `NewsItem`:各源归一化后的条目(RSS / TheNewsAPI / 未来源共用)。
- `NewsProvider`:provider 协议(`fetch` 给定 query/日期窗 → NewsItem 列表)。多源可插拔。
- `BROWSER_UA`:TheNewsAPI 在 Cloudflare 后,默认 urllib UA 触发 403/1010,必须用浏览器 UA。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Cloudflare 反爬:必须浏览器 UA(实测默认/自定义短 UA 触发 403 error code 1010)。
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class NewsItem:
    """各源归一化后的一条新闻。

    asset = 该条对应的 roster 资产 series_id(API 源按资产查询时填;RSS/通用为空,靠分类回填)。
    text  = 抽取的正文(extract 填;失败/未抽则空,降级用 summary)。
    """

    source: str  # 发布方(域名或源名)
    title: str
    link: str
    published: str = ""
    summary: str = ""
    uuid: str = ""  # TheNewsAPI 的文章 id(去重/取详情用)
    asset: str = ""  # roster 资产 series_id(按资产查询时)
    text: str = ""  # 抽取正文


@runtime_checkable
class NewsProvider(Protocol):
    """新闻源协议。`needs_key`=是否依赖 key(缺则跳过);`supports_query`=能否按关键词/日期查(RSS 不能)。"""

    name: str
    needs_key: bool
    supports_query: bool

    def fetch(
        self,
        query: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 25,
    ) -> list[NewsItem]:
        """拉新闻。query/start/end 仅 supports_query 的源有意义;失败应抛异常或返回 []。"""
        ...
