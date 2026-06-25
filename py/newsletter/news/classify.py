"""新闻分类(事实 / 解读 / 影响资产 / 方向)—— 迁自旧 news.py。

复用 LLM provider 的 `call_structured`;无 provider → 返回 None(不分类,新闻仍展示为未分类)。
按模型回填的 `index`(从 1)对齐,免疫 LLM 改写/翻译标题。S5 起喂**抽取的全文**(无则退 summary)。
"""

from __future__ import annotations

from ..llm.providers import select_provider
from ..llm.style import TEXT_STYLE
from .base import NewsItem

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "对应输入列表的编号(从 1 开始),用于对齐——务必填准"},
                    "title": {"type": "string", "description": "原标题(保持英文原文,不要翻译)"},
                    "category": {
                        "type": "string",
                        "enum": ["事实", "解读", "事实+解读", "噪音"],
                        "description": "这条新闻主要是客观事实、主观解读、二者皆有,还是无信息量的噪音",
                    },
                    "summary": {"type": "string", "description": "中文一句话概括"},
                    "affected_assets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "主要受影响资产(如 美债/黄金/美元/美股/A股/比特币)",
                    },
                    "note": {"type": "string", "description": "对资产的方向性影响,简短;非买卖建议"},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "watch"],
                        "description": "该新闻对主要受影响资产的方向性:up=利多/上行,down=利空/下行,watch=方向待观察",
                    },
                    "sentiment": {
                        "type": "number",
                        "description": "对受影响资产的情绪强度 ∈ [-1,1]:-1=极度利空、0=中性、+1=极度利多(比 direction 更细,供量化)",
                    },
                },
                "required": ["index", "title", "category", "summary", "affected_assets", "direction"],
            },
        }
    },
    "required": ["items"],
}

NEWS_SYSTEM = (
    "你是宏观新闻分类助手。把每条新闻分为『事实/解读/事实+解读/噪音』,"
    "用中文一句话概括,列出主要受影响资产,简述方向性影响,给出方向 direction(up/down/watch)"
    "和情绪强度 sentiment ∈ [-1,1](利空为负、利多为正、中性 0,比 direction 更细)。"
    "严格区分客观事实与主观解读;绝不给买/卖建议,不承诺收益。 " + TEXT_STYLE
)


def _body(it: NewsItem) -> str:
    """喂分类的正文:优先抽取全文(截断控上下文),退回 summary。v1.8:Basic 后放宽到 3000 字。"""
    txt = (it.text or "").strip()
    if txt:
        return txt[:3000]
    return it.summary or ""


def classify(items: list[NewsItem]) -> list[dict] | None:
    """逐条分类;无 LLM provider 或无新闻时返回 None。返回与 items 等长的分类列表。"""
    provider = select_provider()
    if provider is None or not items:
        return None
    listing = "\n".join(
        f"{i + 1}. [{it.source}] {it.title}" + (f" — {b}" if (b := _body(it)) else "")
        for i, it in enumerate(items)
    )
    user = (
        "请对以下每条新闻分类。每条返回的 index 必须等于该条前面的编号(从 1 开始),"
        "title 保持英文原文不要翻译,category/summary/note 用中文,direction 用 up/down/watch:\n" + listing
    )
    result = provider.call_structured(
        NEWS_SYSTEM, user, "classify_news", "对新闻逐条分类(事实/解读/影响资产)", NEWS_SCHEMA
    )
    return result.get("items")
