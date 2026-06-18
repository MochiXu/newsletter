"""Twelve Data 数据源。

免费档 800 次/天、8 次/分。本项目主打**黄金现货 `XAU/USD`**(真现货、无分红回溯调整、
值最稳)。免费档不含股指/真 DXY(实测 404),故只用于金属/外汇类。
"""

from __future__ import annotations

import urllib.parse

from .base import FetchError, http_get_json, to_frame

import pandas as pd


class TwelveDataSource:
    name = "twelvedata"
    BASE = "https://api.twelvedata.com/time_series"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def fetch(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if not self.api_key:
            raise FetchError("Twelve Data api_key 缺失")
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 5000,
            "order": "ASC",
            "apikey": self.api_key,
        }
        if start:
            params["start_date"] = start
        if end:
            params["end_date"] = end
        data = http_get_json(self.BASE + "?" + urllib.parse.urlencode(params))
        if not isinstance(data, dict):
            raise FetchError(f"Twelve Data {symbol}: 非预期响应")
        if data.get("status") == "error":
            raise FetchError(f"Twelve Data {symbol}: {str(data.get('message'))[:80]}")
        values = data.get("values") or []
        pairs = [(v["datetime"], v.get("close")) for v in values if v.get("datetime")]
        return to_frame(pairs)
