"""FRED 数据源(St. Louis Fed)。

权威、免费、无硬性日限额。主打利率/利差/实际利率/广义美元/VIX/月频宏观。
日频值缺失以 `"."` 表示(节假日等),跳过。
"""

from __future__ import annotations

import urllib.parse

from .base import FetchError, http_get_json, to_frame

import pandas as pd


class FredSource:
    name = "fred"
    BASE = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def fetch(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if not self.api_key:
            raise FetchError("FRED api_key 缺失")
        params = {"series_id": symbol, "api_key": self.api_key, "file_type": "json"}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        data = http_get_json(self.BASE + "?" + urllib.parse.urlencode(params))
        if isinstance(data, dict) and data.get("error_message"):
            raise FetchError(f"FRED {symbol}: {data['error_message'][:80]}")
        obs = data.get("observations", []) if isinstance(data, dict) else []
        pairs = [
            (o["date"], o["value"])
            for o in obs
            if o.get("value") not in (".", "", None)
        ]
        return to_frame(pairs)
