"""新闻正文抽取(v1.6 S5):从 url 抓全文(API 只给 ~160 字)。

- 首选 `trafilatura`(去导航/广告/页脚,留主文);缺失/抽空 → stdlib 启发式去标签。
- **死链/取不到/抽空 → 丢弃**(返回 None,上层 enrich 跳过该条),绝不阻断管线。
- 浏览器 UA(很多新闻站 Cloudflare/反爬);缓存命中不重抓(护配额 + 礼貌)。
- **版权**:抓来的全文仅内部喂 LLM + 派生特征;对外产物只展示 标题/来源/链接/我们的摘要,绝不复制正文。
"""

from __future__ import annotations

import logging
import re
import urllib.request

from .base import BROWSER_UA, NewsItem

try:  # 可选依赖;缺失则降级
    import trafilatura  # type: ignore
except Exception:  # noqa: BLE001
    trafilatura = None

log = logging.getLogger(__name__)

_MAX_CHARS = 4000  # 喂 LLM 的正文上限(控成本/上下文)
_MIN_CHARS = 120   # 低于此视为抽取失败(paywall 残文/空)→ 丢
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", text or "").strip()[:_MAX_CHARS]


def _fetch_html(url: str, timeout: int = 10) -> str | None:
    """GET html(浏览器 UA + 1 次重试)。任何失败(404/403/超时)返回 None。"""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 — 死链/反爬/超时都丢
            if attempt == 0:
                continue
            log.debug("extract fetch failed %s: %s", url, e)
            return None
    return None


def _heuristic(html: str) -> str:
    """stdlib 兜底:去 script/style + 去标签 + 压空白(粗糙,trafilatura 缺失时用)。"""
    return _clean(_TAG.sub(" ", _SCRIPT.sub(" ", html or "")))


def extract(url: str) -> str | None:
    """抓 url 正文并清洗。死链/抽空/过短 → None(上层丢弃)。"""
    if not url:
        return None
    html = _fetch_html(url)
    if not html:
        return None
    text = ""
    if trafilatura is not None:
        try:
            text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        except Exception:  # noqa: BLE001
            text = ""
    if not text:
        text = _heuristic(html)
    text = _clean(text)
    return text if len(text) >= _MIN_CHARS else None


def enrich(items: list[NewsItem], cache=None, drop_on_fail: bool = True) -> list[NewsItem]:
    """逐条抓正文填 `item.text`;缓存命中不重抓。

    drop_on_fail=True:抽取失败(死链/反爬/空)→ 丢弃该条(用户要求"访问不到直接丢")。
    False:保留(text 空,分类时退回 summary)。
    """
    out: list[NewsItem] = []
    dropped = 0
    for it in items:
        key = it.uuid or it.link
        text = cache.get(key) if cache else None
        if text is None:
            text = extract(it.link)
            if text and cache:
                cache.put(key, text)
        if text:
            it.text = text
            out.append(it)
        elif not drop_on_fail:
            out.append(it)
        else:
            dropped += 1
    if dropped:
        log.info("news extract: 丢弃 %s 条死链/抽取失败,保留 %s 条", dropped, len(out))
    return out
