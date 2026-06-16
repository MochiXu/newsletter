"""生成四层简报 —— 底层可换大模型(见 providers.py)。

无任何已配置的 LLM provider 时返回 None,调用方走「仅事实层」回退。
"""

from __future__ import annotations

from .providers import select_provider


def generate_brief(data_block: str, linkage_map: str) -> dict | None:
    """生成四层简报 dict;未配置任何 LLM provider 时返回 None。"""
    provider = select_provider()
    if provider is None:
        return None
    return provider.generate(data_block, linkage_map)
