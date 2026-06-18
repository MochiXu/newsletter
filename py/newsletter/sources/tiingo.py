"""Tiingo 数据源(EOD)。

免费档 1000 次/天,历史很长:`SPY`(1993)、`QQQ`(1999)、`GLD`(2004)、
`UUP`(2007,美元指数 ETF→窄口径 DXY 代理)、`IEF`(2002)。

**用未复权 `close`** 而非 `adjClose`:adjClose 随分红回溯调整(整段历史会微变),违背
「历史不变」假设;且代理类只比收益率/趋势/标准化,价格指数口径用 close 更对。
"""

from __future__ import annotations

import urllib.parse

from .base import FetchError, http_get_json, to_frame

import pandas as pd


class TiingoSource:
    name = "tiingo"
    BASE = "https://api.tiingo.com/tiingo/daily/{symbol}/prices"

    def __init__(self, token: str | None):
        self.token = token

    def fetch(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if not self.token:
            raise FetchError("Tiingo token 缺失")
        params = {"token": self.token, "format": "json"}
        if start:
            params["startDate"] = start
        if end:
            params["endDate"] = end
        url = self.BASE.format(symbol=urllib.parse.quote(symbol)) + "?" + urllib.parse.urlencode(params)
        data = http_get_json(url)
        if isinstance(data, dict):  # Tiingo 错误是 dict({"detail": ...});正常是 list
            raise FetchError(f"Tiingo {symbol}: {str(data.get('detail') or data)[:80]}")
        pairs = [(d["date"][:10], d.get("close")) for d in data if d.get("date")]
        return to_frame(pairs)
