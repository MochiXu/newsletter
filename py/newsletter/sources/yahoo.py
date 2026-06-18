"""Yahoo Finance 数据源(免鉴权 chart 端点)——仅作**兜底**。

非官方端点,会限流/可能变结构,故只在主源(FRED/TwelveData/Tiingo)全部失败时降级使用。
"""

from __future__ import annotations

import datetime
import urllib.parse

from .base import FetchError, http_get_json, to_frame

import pandas as pd


class YahooSource:
    name = "yahoo"
    BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    def fetch(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        params: dict[str, object] = {"interval": "1d"}
        if start or end:
            params["period1"] = _to_epoch(start, default=0)
            params["period2"] = _to_epoch(end, default=_now_epoch())
        else:
            params["range"] = "10y"
        url = self.BASE.format(symbol=urllib.parse.quote(symbol)) + "?" + urllib.parse.urlencode(params)
        data = http_get_json(url)
        try:
            result = data["chart"]["result"][0]
            stamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
        except (KeyError, TypeError, IndexError):
            raise FetchError(f"Yahoo {symbol}: 非预期响应结构") from None
        pairs = [
            (datetime.datetime.utcfromtimestamp(t).date().isoformat(), c)
            for t, c in zip(stamps, closes)
            if c is not None
        ]
        return to_frame(pairs)


def _to_epoch(date_str: str | None, default: int) -> int:
    if not date_str:
        return default
    return int(datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def _now_epoch() -> int:
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())
