"""四层简报的 LLM 契约:JSON Schema(emit_brief)+ system 提示。

四层结构是简报的灵魂(事实/解读/可证伪假设/影响观察点),也是合规外衣与给 LLM 的缰绳。
本次重构把「数据由代码算成技术特征」前置,故 system 明确要求 LLM **基于给定特征解读、
不要自行心算**。
"""

from __future__ import annotations

BRIEF_TOOL = "emit_brief"

# emit_brief 的 JSON Schema —— Anthropic 作 tool input_schema,OpenAI 兼容作 function parameters。
BRIEF_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "一句话总览今日宏观图景"},
        "tone": {
            "type": "string",
            "enum": ["risk-on", "risk-off", "neutral"],
            "description": "当日整体基调:risk-on=风险偏好上升;risk-off=避险上升;neutral=中性观望",
        },
        "facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "事实层:纯客观,复述给定的数据/特征,不加判断。每条一句话,不要包成对象",
        },
        "interpretation": {
            "type": "array",
            "items": {"type": "string"},
            "description": "解读层:当前处于什么 regime、特征含义。必须是判断而非事实",
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
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "watch"],
                        "description": "方向性观察:up=偏多/上行风险,down=偏空/下行风险,watch=待观察",
                    },
                },
                "required": ["asset", "watch", "direction"],
            },
            "description": "影响层:对相关资产的观察点(绝非投资建议)",
        },
    },
    "required": ["headline", "tone", "facts", "interpretation", "hypotheses", "impact"],
}

SYSTEM = (
    "你是一名严谨的宏观研究助手,服务于个人投资者的学习与决策框架。"
    "你会收到:今日各资产的**已由代码计算好的技术特征**(收益率/变化量/均线/波动率/相关性/"
    "z-score/regime 标签等)、月频宏观最新读数、以及一份『宏观传导图』。"
    "硬性纪律:(1) 基于给定特征推理,**不要自行心算或臆造数字**;(2) 严格区分事实与判断;"
    "(3) 假设必须可证伪(给出失效条件);(4) 只给『观察点』,绝不给买/卖建议,不承诺收益;"
    "(5) 中文输出,简洁、有信息量;(6) 给出当日 tone,并为每条影响层资产标注 direction。"
    "通过 emit_brief 输出四层简报。"
)
