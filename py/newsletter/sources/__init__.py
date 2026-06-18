"""数据源适配层:每家一个 Source,统一产出 tidy DataFrame[date, value]。

逻辑指标 → 物理来源的映射与兜底链在 `newsletter.catalog`。
"""

from .base import FetchError, Source, http_get_json
from .fred import FredSource
from .tiingo import TiingoSource
from .twelvedata import TwelveDataSource
from .yahoo import YahooSource

__all__ = [
    "FetchError",
    "Source",
    "http_get_json",
    "FredSource",
    "TiingoSource",
    "TwelveDataSource",
    "YahooSource",
]
