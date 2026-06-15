"""调用 Anthropic Messages API 生成四层简报(纯标准库 urllib,无第三方依赖)。

通过 tool_use 强制结构化输出(emit_brief 工具)。
无 ANTHROPIC_API_KEY 时返回 None,调用方走「仅事实层」回退。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"

# 四层结构的 JSON Schema —— 作为工具的 input_schema,强制模型按此结构输出。
BRIEF_TOOL = {
    "name": "emit_brief",
    "description": "输出四层结构的每日宏观简报",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string", "description": "一句话总览今日宏观图景"},
            "facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "事实层:纯客观,只基于给定数据,不加判断",
            },
            "interpretation": {
                "type": "array",
                "items": {"type": "string"},
                "description": "解读层:当前处于什么 regime、偏离含义。必须是判断而非事实",
            },
            "hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "if_then": {"type": "string", "description": "若 X 则预期 Y"},
                        "invalidation": {"type": "string", "description": "失效条件 Z"},
                    },
                    "required": ["if_then", "invalidation"],
                },
                "description": "假设层:可证伪命题,每条必须带失效条件",
            },
            "impact": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset": {"type": "string"},
                        "watch": {"type": "string", "description": "观察点,不是买卖建议"},
                    },
                    "required": ["asset", "watch"],
                },
                "description": "影响层:对相关资产的观察点(绝非投资建议)",
            },
        },
        "required": ["headline", "facts", "interpretation", "hypotheses", "impact"],
    },
}

SYSTEM = (
    "你是一名严谨的宏观研究助手,服务于个人投资者的学习与决策框架。"
    "硬性纪律:(1) 严格区分事实与判断;(2) 假设必须可证伪(给出失效条件);"
    "(3) 只给『观察点』,绝不给买/卖建议,不承诺收益;(4) 中文输出,简洁、有信息量。"
    "你会得到今日宏观数据与一份『宏观传导图』,据此推理并通过 emit_brief 工具输出四层简报。"
)


def generate_brief(data_block: str, linkage_map: str, model: str | None = None) -> dict | None:
    """生成四层简报 dict;无 ANTHROPIC_API_KEY 时返回 None。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    user = (
        "## 今日宏观数据\n"
        + data_block
        + "\n\n## 宏观传导图(你的推理依据)\n"
        + linkage_map
        + "\n\n请基于以上,通过 emit_brief 工具输出四层简报。"
        "事实层只复述数据;解读层标注为判断;假设层给可证伪命题与失效条件;影响层给观察点。"
    )
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": SYSTEM,
        "tools": [BRIEF_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_brief"},
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Anthropic API {e.code}: {detail}") from e

    for block in body.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == "emit_brief":
            return block["input"]
    raise RuntimeError("Anthropic 响应未包含 emit_brief 工具调用")
