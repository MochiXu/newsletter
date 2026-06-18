"""数据源统一接口 + HTTP 工具(纯 stdlib urllib;数据帧用 pandas)。

每个 Source 适配一家 API,`fetch(symbol, start, end)` 产出统一 tidy 帧:
列 `date`(YYYY-MM-DD 字符串,升序)、`value`(float)。失败抛 `FetchError`,
由上层(catalog)捕获后走兜底链。

安全:HTTP 错误信息**只保留 URL 的 path 部分**(去掉 query string)——FRED/Tiingo/
Twelve Data 把 api_key 放在 query 里,绝不能泄漏进日志/异常。
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

import pandas as pd

log = logging.getLogger(__name__)

# 可重试的 HTTP 状态码(限流 / 网关 / 服务端瞬时故障)。其余(如 404 符号不存在)立即失败。
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# tidy 帧的列契约。
DATE = "date"
VALUE = "value"


class FetchError(Exception):
    """数据源拉取失败(重试耗尽或不可重试错误)。"""


@runtime_checkable
class Source(Protocol):
    """数据源协议:给定物理 symbol 返回升序的 [date, value] 日频序列。"""

    name: str

    def fetch(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame: ...


def _safe_url(url: str) -> str:
    """去掉 query string(含 api_key),供日志/异常使用。"""
    return url.split("?", 1)[0]


def http_get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
    backoff: float = 1.5,
) -> dict | list:
    """GET 一个 JSON 端点,带指数退避重试。key 不入异常信息。"""
    hdrs = {"User-Agent": "newsletter/2.0 (+research)"}
    if headers:
        hdrs.update(headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = RuntimeError(f"HTTP {e.code}")
            if e.code not in _RETRYABLE_STATUS:
                raise FetchError(f"{_safe_url(url)} -> HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_err = e
        if attempt < retries - 1:
            delay = backoff * (2**attempt)
            log.debug("retry %s/%s after %.1fs: %s", attempt + 1, retries, delay, _safe_url(url))
            time.sleep(delay)
    raise FetchError(f"{_safe_url(url)} failed after {retries} tries: {last_err}")


def to_frame(pairs: list[tuple[str, float]]) -> pd.DataFrame:
    """把 (date, value) 列表整理成升序、去重、去缺失的 tidy 帧。"""
    df = pd.DataFrame(pairs, columns=[DATE, VALUE])
    if df.empty:
        return df
    df[VALUE] = pd.to_numeric(df[VALUE], errors="coerce")
    df = df.dropna(subset=[VALUE])
    df = df.drop_duplicates(subset=[DATE], keep="last").sort_values(DATE, ignore_index=True)
    return df
