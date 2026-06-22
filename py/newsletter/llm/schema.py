"""四层简报的 LLM 契约:JSON Schema(emit_brief)+ system 提示。

四层结构是简报的灵魂(事实/解读/可证伪假设/影响观察点),也是合规外衣与给 LLM 的缰绳。
本次重构把「数据由代码算成技术特征」前置,故 system 明确要求 LLM **基于给定特征解读、
不要自行心算**。
"""

from __future__ import annotations

from .. import catalog
from ..models import FACT_TAGS
from .style import TEXT_STYLE

BRIEF_TOOL = "emit_brief"

# 预测 roster(单一事实源 = catalog.PREDICTION_TARGETS):约束假设层「不超不漏」。
_PRED = [(s.series_id, s.metric_label or s.label) for s in catalog.PREDICTION_TARGETS]
_PRED_IDS = [sid for sid, _ in _PRED]
_PRED_N = len(_PRED_IDS)
_PRED_DESC = "、".join(f"{lab}={sid}" for sid, lab in _PRED)

# 主题标签受控词表单一源在 models.FACT_TAGS(coercion 落库时也按它兜底,避免越界 tag)。
_TAG_ENUM = list(FACT_TAGS)

# 事实层/解读层正文里"需要上色强调的关键数字"——**扁平字符串**(避免 DeepSeek 处理不了的深层嵌套数组)。
# 格式 'token|dir;token|dir',dir∈up/down/flat;后端 _coerce_tagged_list 解析成 figures 列表给前端。
_FIGS_PROP: dict = {
    "type": "string",
    "description": (
        "需上色强调的关键数字,格式 'token|dir;token|dir'(分号分隔)。"
        "**token 必须是数字连同它紧跟的单位一起**(百分号、bp 不能漏!如 '-7.8%' 不是 '7.8'、'+15bp' 不是 '15'、"
        "纯点数如 '80.48' 才不带单位);**不要用资产名**(不要写 '标普500'、'VIX'、'纳指');"
        "token 须是 text 中的原样子串(text 里是 '7.8%' 就写 '7.8%')。"
        "dir∈up(上行/增大,绿)/down(下行/减小,红)/flat(中性)。"
        "**只列有方向含义的变化**(涨跌/扩大收窄),电平/相关系数/窗口天数不列,不必每个数字都列;无则留空串。"
        "例:text='标普涨80.48点,VIX升2.03,黄金跌7.8%' → figs='80.48|up;2.03|up;7.8%|down'。"
    ),
}

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
            "description": (
                "事实层:**精选**关键客观观察 + 当日事件(不要逐条复述每个收盘价——它们已在数据表)。"
                "每条 {tag, text}:tag 从枚举选最贴切的一个主题;text 为一句客观陈述,可含具体数字,不加判断"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "enum": _TAG_ENUM, "description": "主题标签(枚举择一)"},
                    "text": {"type": "string", "description": "一句客观陈述,可含数字;不加判断"},
                    "figs": _FIGS_PROP,
                },
                "required": ["tag", "text"],
            },
        },
        "interpretation": {
            "type": "array",
            "description": "解读层:因果/机制论述(判断,非事实)。每条 {tag, text},tag = 该判断主要针对的主题",
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "enum": _TAG_ENUM, "description": "该判断主要针对的主题(枚举择一)"},
                    "text": {"type": "string", "description": "一段论述:当前 regime / 特征含义 / 因果机制"},
                    "figs": _FIGS_PROP,
                },
                "required": ["tag", "text"],
            },
        },
        "hypotheses": {
            "type": "array",
            "minItems": _PRED_N,
            "maxItems": _PRED_N,
            "description": (
                f"假设层 = 对固定 {_PRED_N} 个方向各给且只给一条由特征驱动的预测;"
                f"asset 必须恰好覆盖且不重复:{_PRED_DESC}。禁止凑数;低把握给低 confidence;"
                "失效条件须可度量(绑定该序列+具体阈值+期限)"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "asset": {"type": "string", "enum": _PRED_IDS, "description": "预测对象(固定 roster,不可重复)"},
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "flat"],
                        "description": "未来方向:up=上行,down=下行,flat=横盘/中性",
                    },
                    "horizon": {
                        "type": "string",
                        "enum": ["next_1d", "h_5d", "h_20d", "h_60d"],
                        "description": "预测期限(交易日):次日/5日/20日/60日",
                    },
                    "confidence": {"type": "number", "description": "0~1 置信度(用于校准);低把握就给低值,别都给高"},
                    "key_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "驱动该预测的具体特征/读数(取自给定特征块)",
                    },
                    "if_then": {"type": "string", "description": "人读:若 X(具体阈值)则预期 Y"},
                    "invalidation": {
                        "type": "string",
                        "description": "可度量失效条件:绑定该序列+具体阈值+期限,能被未来数据客观判定",
                    },
                },
                "required": ["asset", "direction", "horizon", "confidence", "key_factors", "if_then", "invalidation"],
            },
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
    "硬性纪律:(1) 基于给定特征推理,**不要自行心算或臆造数字**;"
    "(2) 严格区分事实与判断;事实层只放**精选**的关键客观观察+事件(别复述每个收盘价,数据表已有),"
    "每条带主题标签 tag;解读层是因果/机制判断,每条也带 tag(从受控词表择一);"
    "事实层/解读层可为正文里**有方向含义的关键变化数字**填 figs(扁平字符串 'token|dir;...',"
    "token 是数字本身如 '+15bp'/'-7.8%'、不是资产名,dir=up/down/flat),只标变化、不标电平/相关系数;"
    f"(3) **假设层 = 对固定 roster({_PRED_DESC})各给且只给一条由特征驱动的预测**:"
    "写明方向(up/down/flat)、期限 horizon、置信度 confidence(0~1)、驱动特征 key_factors、"
    "以及**可度量的失效条件**(绑定该序列+具体阈值+期限,能被未来数据客观判定);"
    "**不要凑数、不要超出或漏掉这几个方向**,低把握就给低 confidence;"
    "(4) 只给『观察点』,绝不给买/卖建议,不承诺收益;(5) 中文输出,简洁、有信息量;"
    "(6) 给出当日 tone,并为每条影响层资产标注 direction。通过 emit_brief 输出四层简报。"
    " " + TEXT_STYLE
)
