"""pydantic 数据模型(边界契约)。

两类:
1. **LLM 原始输出**(`LLMBrief` 等):容错解析模型回填的四层简报——含归一化
   (modeled 偶尔把 `["x"]` 返成 `[{"fact": "x"}]`,这里统一抽成字符串,根治旧版
   `[object Object]` bug)与枚举容错(tone/direction 用下划线/大小写也能落位)。
2. **前端契约**(`Brief` 等):严格对应 `frontend/app/src/types.ts`,emit 时用驼峰别名。

原始时序数据(observations)是大体量 DataFrame,不套 pydantic(见 store/features)。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── 枚举(值严格对齐前端 types.ts)──────────────────────────────────────────


class Tone(str, Enum):
    RISK_ON = "risk-on"
    RISK_OFF = "risk-off"
    NEUTRAL = "neutral"


class Dir(str, Enum):
    UP = "up"
    DOWN = "down"
    WATCH = "watch"


class MetricKind(str, Enum):
    YIELD = "yield"
    SPREAD = "spread"
    INDEX = "index"
    PRICE = "price"


class NewsCat(str, Enum):
    FACT = "fact"
    READ = "read"
    BOTH = "both"
    NOISE = "noise"


class ReviewStatus(str, Enum):
    HELD = "held"
    INVALIDATED = "invalidated"
    OPEN = "open"


class PredDir(str, Enum):
    """预测方向(用于固定 roster 的假设/判断)。"""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class Horizon(str, Enum):
    """预测期限(交易日)枚举——固定档便于回测跨日聚合。"""

    NEXT_1D = "next_1d"
    H_5D = "h_5d"
    H_20D = "h_20d"
    H_60D = "h_60d"


# ── 归一化辅助 ──────────────────────────────────────────────────────────


def _coerce_str_list(v: Any) -> list[str]:
    """把 LLM 返回的 facts/interpretation 统一成 list[str]。

    容忍 `["x"]`、`[{"fact": "x"}]`、`[{"interpretation": "x"}]`、单值 dict 等;
    丢弃空白项。这是根治旧版把 dict 直接 dump 成 `{'fact': ...}` 的关键。
    """
    if v is None:
        return []
    if isinstance(v, (str, dict)):
        v = [v]
    out: list[str] = []
    for item in v:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            for key in ("fact", "interpretation", "text", "value", "content"):
                if key in item:
                    text = str(item[key])
                    break
            else:
                text = str(next(iter(item.values()))) if len(item) == 1 else str(item)
        else:
            text = str(item)
        text = text.strip()
        if text:
            out.append(text)
    return out


# 事实层/解读层主题标签受控词表(单一事实源)。schema 喂给 LLM 作 enum;coercion 落库时兜底。
FACT_TAGS: tuple[str, ...] = ("股市", "利率", "曲线", "美元", "黄金", "波动", "相关", "宏观", "事件")


def _parse_figs(v: Any) -> list[dict[str, str]]:
    """把 LLM 的扁平 figs 字符串 'token|dir;token|dir' 解析成 [{t,dir}];已是 list 则透传。

    扁平字符串避免了 DeepSeek 处理不了的"数组套对象再套数组"深层嵌套;前端契约仍是 figures:[{t,dir}]。
    """
    if isinstance(v, list):
        return v
    if not isinstance(v, str):
        return []
    out: list[dict[str, str]] = []
    for part in v.split(";"):
        part = part.strip()
        if not part:
            continue
        t, _, d = part.partition("|")
        t = t.strip()
        if t:
            out.append({"t": t, "dir": d.strip().lower()})  # dir 由 Figure 校验器兜底
    return out


def _coerce_tagged_list(v: Any) -> list[dict[str, str]]:
    """把 facts/interpretation 统一成 [{tag, text}]。

    容忍:纯字符串(tag 置空,**向后兼容旧 str[] 契约/降级**)、{tag,text}、
    {fact/interpretation/value/content}、单值 dict、以及已是 TaggedItem 实例(再校验路径)。
    tag 不在 FACT_TAGS 内 → 归空(与 schema 枚举对齐);丢弃 text 为空的项。
    """
    if v is None:
        return []
    if isinstance(v, (str, dict)) or isinstance(v, BaseModel):
        v = [v]
    out: list[dict[str, Any]] = []
    for item in v:
        if isinstance(item, BaseModel):
            item = item.model_dump()  # TaggedItem 实例 → {tag,text,figures}(build_brief 再校验路径)
        tag, text, figures = "", "", []
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            tag = str(item.get("tag") or item.get("theme") or "").strip()
            # figs 为扁平字符串(LLM 友好);figures 为已结构化列表(再校验/直接构造)
            figures = _parse_figs(item["figs"] if item.get("figs") is not None else item.get("figures"))
            for key in ("text", "fact", "interpretation", "value", "content"):
                if item.get(key):
                    text = str(item[key])
                    break
            else:
                skip = ("tag", "theme", "figures")
                vals = [str(val) for k, val in item.items() if k not in skip and val]
                text = vals[0] if len(vals) == 1 else " ".join(vals)
        else:
            text = str(item)
        text = text.strip()
        if text:
            out.append({"tag": tag if tag in FACT_TAGS else "", "text": text, "figures": figures})
    return out


def _coerce_tone(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower().replace("_", "-")
    return v


def _coerce_dir(v: Any) -> Any:
    if isinstance(v, str):
        s = v.strip().lower()
        return s if s in ("up", "down", "watch") else "watch"
    return "watch"


def _coerce_pred_dir(v: Any) -> Any:
    if isinstance(v, str):
        s = v.strip().lower()
        return s if s in ("up", "down", "flat") else "flat"
    return "flat"


def _coerce_horizon(v: Any) -> Any:
    if isinstance(v, str):
        s = v.strip().lower().replace("-", "_")
        return s if s in ("next_1d", "h_5d", "h_20d", "h_60d") else "h_20d"
    return "h_20d"


def _coerce_conf(v: Any) -> float:
    """置信度归一到 [0,1];模型偶尔给 0~100 则除以 100;不可解析归 0。"""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    if x > 1.0:
        x = x / 100.0
    return max(0.0, min(1.0, x))


# ── LLM 原始输出(容错)──────────────────────────────────────────────────


class Figure(BaseModel):
    """text 中需上色强调的一个关键数字。t=该数字在 text 中的原样子串,dir=方向(up绿/down红/flat中性)。"""

    model_config = ConfigDict(extra="ignore")
    t: str = ""
    dir: PredDir = PredDir.FLAT

    @field_validator("dir", mode="before")
    @classmethod
    def _d(cls, v: Any) -> Any:
        return _coerce_pred_dir(v)


class TaggedItem(BaseModel):
    """带主题标签的条目(事实层/解读层一条)。tag=主题(可空),text=正文,figures=需上色的关键数字。"""

    model_config = ConfigDict(extra="ignore")
    tag: str = ""
    text: str = ""
    figures: list[Figure] = Field(default_factory=list)


class LLMHypothesis(BaseModel):
    """一条对固定 roster 方向的、由特征驱动的可证伪预测(对应 emit_brief.hypotheses)。"""

    model_config = ConfigDict(extra="ignore")
    asset: str = ""  # 预测对象(catalog.PREDICTION_TARGET_IDS 之一)
    direction: PredDir = PredDir.FLAT
    horizon: Horizon = Horizon.H_20D
    confidence: float = 0.0
    key_factors: list[str] = Field(default_factory=list)
    if_then: str = ""
    invalidation: str = ""

    @field_validator("direction", mode="before")
    @classmethod
    def _dir(cls, v: Any) -> Any:
        return _coerce_pred_dir(v)

    @field_validator("horizon", mode="before")
    @classmethod
    def _hz(cls, v: Any) -> Any:
        return _coerce_horizon(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        return _coerce_conf(v)

    @field_validator("key_factors", mode="before")
    @classmethod
    def _kf(cls, v: Any) -> list[str]:
        return _coerce_str_list(v)


class LLMImpact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    asset: str = ""
    watch: str = ""
    direction: Dir = Dir.WATCH

    @field_validator("direction", mode="before")
    @classmethod
    def _dir(cls, v: Any) -> Any:
        return _coerce_dir(v)


class LLMBrief(BaseModel):
    """LLM 四层简报的容错解析模型(对应 emit_brief schema)。"""

    model_config = ConfigDict(extra="ignore")

    headline: str = ""
    tone: Tone = Tone.NEUTRAL
    facts: list[TaggedItem] = Field(default_factory=list)
    interpretation: list[TaggedItem] = Field(default_factory=list)
    hypotheses: list[LLMHypothesis] = Field(default_factory=list)
    impact: list[LLMImpact] = Field(default_factory=list)

    @field_validator("facts", "interpretation", mode="before")
    @classmethod
    def _tagged_list(cls, v: Any) -> list[dict[str, str]]:
        return _coerce_tagged_list(v)

    @field_validator("tone", mode="before")
    @classmethod
    def _tone(cls, v: Any) -> Any:
        return _coerce_tone(v)


# ── 前端契约(严格对齐 types.ts;emit 用驼峰别名)─────────────────────────


class _CamelModel(BaseModel):
    """前端契约基类:允许按字段名构造,emit 时用别名(驼峰)。"""

    model_config = ConfigDict(populate_by_name=True)


class PricePoint(_CamelModel):
    """价格/走势序列一个点(供前端指标 sparkline 与 30 日价格大图)。"""

    date: str
    value: float


class Metric(_CamelModel):
    key: str
    label: str
    value: float
    change: float
    kind: MetricKind
    spark: list[PricePoint] = Field(default_factory=list)  # 最近~20真实收盘点(带日期,因果),前端画 sparkline+hover


class Signal(_CamelModel):
    """技术指标一条(代码计算,signals 块)。value 的解读由 unit 决定。"""

    key: str
    label: str
    value: float
    unit: str  # pct=带符号% | pct0=无符号% | bp | z | corr | yield=电平%
    group: str  # trend | momentum | vol | rates | dollar | cross_asset | range


class Hypothesis(_CamelModel):
    if_then: str = Field(alias="ifThen")
    invalidation: str
    asset: str = ""
    direction: PredDir = PredDir.FLAT
    horizon: Horizon = Horizon.H_20D
    confidence: float = 0.0
    key_factors: list[str] = Field(default_factory=list, alias="keyFactors")


class Impact(_CamelModel):
    asset: str
    watch: str
    dir: Dir


class Review(_CamelModel):
    if_then: str = Field(alias="ifThen")
    status: ReviewStatus
    note: str = ""


class News(_CamelModel):
    title: str
    source: str
    cat: NewsCat | None = None  # None = 未分类(无 LLM provider)
    assets: list[str] = Field(default_factory=list)
    dir: Dir = Dir.WATCH
    link: str = ""


class Brief(_CamelModel):
    date: str
    weekday: str
    issue: int = 0
    time: str = "07:00 CST"
    tone: Tone = Tone.NEUTRAL
    headline: str = ""
    metrics: list[Metric] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)  # 技术指标(代码计算)
    regime: dict[str, str] = Field(default_factory=dict)  # 代码派生的 regime 标签
    price_series: dict[str, list[PricePoint]] = Field(
        default_factory=dict, alias="priceSeries"
    )  # 30日价格大图序列,key=metric.key(chart 资产)
    facts: list[TaggedItem] = Field(default_factory=list)  # 事实层(带主题标签)
    reads: list[TaggedItem] = Field(default_factory=list)  # 解读层(后端 interpretation,带主题标签)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    impacts: list[Impact] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    news: list[News] = Field(default_factory=list)

    @field_validator("facts", "reads", mode="before")
    @classmethod
    def _tagged(cls, v: Any) -> list[dict[str, str]]:
        # 向后兼容:旧 briefs.json 的 facts/reads 为 str[];upsert 会逐条 model_validate 历史日报,
        # 没有这个校验器会在旧数据上抛 ValidationError。也归一化 tag、接受 TaggedItem 实例。
        return _coerce_tagged_list(v)

    def to_json_obj(self) -> dict[str, Any]:
        """emit 为前端 JSON(驼峰键、枚举取值)。"""
        return self.model_dump(by_alias=True, mode="json")


class BriefsPayload(_CamelModel):
    model: str
    generated_at: str = Field(alias="generatedAt")
    briefs: list[Brief] = Field(default_factory=list)

    def to_json_obj(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")
