"""生成四层简报:provider + schema + 特征化 prompt → 经 pydantic 校验的 LLMBrief。

无任何已配置 provider 时返回 None / 空 dict,调用方走「仅事实层 + 特征」降级。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from ..models import LLMBrief
from .prompt import build_user
from .providers import select_provider, select_providers
from .schema import BRIEF_SCHEMA, BRIEF_TOOL, SYSTEM

log = logging.getLogger(__name__)

_DESC = "输出四层结构的每日宏观简报"


def generate_brief(feature_block: str, linkage_map: str) -> LLMBrief | None:
    """据特征块 + 传导图生成四层简报(单模型);未配置 provider 返回 None。"""
    provider = select_provider()
    if provider is None:
        return None
    user = build_user(feature_block, linkage_map)
    raw = provider.call_structured(SYSTEM, user, BRIEF_TOOL, _DESC, BRIEF_SCHEMA)
    return LLMBrief.model_validate(raw)


def generate_briefs(feature_block: str, linkage_map: str) -> dict[str, LLMBrief]:
    """多模型:对 `select_providers()` 里每个模型各生成一份四层简报,返回 {model_id: LLMBrief}(有序)。

    每个模型独立 try/except——某个模型失败只跳过它,不影响其余模型(优雅降级)。
    都没配置/全失败则返回空 dict,调用方走特征层降级。
    """
    out: dict[str, LLMBrief] = {}
    providers = select_providers()
    if not providers:
        return out
    user = build_user(feature_block, linkage_map)
    # 各模型相互独立 → 并发调用(每天 LLM 墙钟从「三者之和」降到「三者最大值」);
    # 每个 provider 内部已带退避重试 + 模型回退(见 providers._call_with_fallback)。
    with ThreadPoolExecutor(max_workers=len(providers)) as ex:
        futures = {
            p.name: ex.submit(p.call_structured, SYSTEM, user, BRIEF_TOOL, _DESC, BRIEF_SCHEMA)
            for p in providers
        }
    for p in providers:  # 按 providers 顺序收集,保证 [0]=主模型(视图顺序稳定)
        try:
            out[p.name] = LLMBrief.model_validate(futures[p.name].result())
        except Exception as e:  # noqa: BLE001 — 单模型失败降级,不阻断其余模型
            log.warning("模型 %s 生成失败,跳过: %s", p.name, e)
    return out
