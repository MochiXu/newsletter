"""多模型 provider 抽象:把「生成四层简报」统一成一个接口,可换底层大模型。

支持:
- anthropic       : Claude Messages API + tool use(强制 emit_brief)
- openai          : OpenAI Chat Completions + function calling
- minimax/deepseek/moonshot/zhipu : 同为 OpenAI 兼容端点(预设 base_url)
- openai-compat   : 任意 OpenAI 兼容端点(LLM_BASE_URL + LLM_API_KEY + LLM_MODEL)

选择(env):
- LLM_PROVIDER 显式指定(如 openai / minimax);缺省则按存在的 key 自动探测
- 各 provider 读自己的 key/model(见 PRESETS / .env.example)

纯标准库(urllib),无第三方依赖。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# 四层结构的 JSON Schema —— Anthropic 作 tool input_schema,OpenAI 兼容作 function parameters。
BRIEF_SCHEMA = {
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
}

SYSTEM = (
    "你是一名严谨的宏观研究助手,服务于个人投资者的学习与决策框架。"
    "硬性纪律:(1) 严格区分事实与判断;(2) 假设必须可证伪(给出失效条件);"
    "(3) 只给『观察点』,绝不给买/卖建议,不承诺收益;(4) 中文输出,简洁、有信息量。"
    "你会得到今日宏观数据与一份『宏观传导图』,据此推理并通过 emit_brief 输出四层简报。"
)


def build_user(data_block: str, linkage_map: str) -> str:
    return (
        "## 今日宏观数据\n"
        + data_block
        + "\n\n## 宏观传导图(你的推理依据)\n"
        + linkage_map
        + "\n\n请基于以上,通过 emit_brief(工具/函数)输出四层简报。"
        "事实层只复述数据;解读层标注为判断;假设层给可证伪命题与失效条件;影响层给观察点。"
        "若你的接口不支持函数调用,请直接输出符合 emit_brief 参数结构的 JSON,不要包裹多余文字。"
    )


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{url} 返回 {e.code}: {detail}") from e


def _extract_json(text: str) -> dict:
    """从模型文本里抠出 JSON 对象(容忍 ```json 围栏与前后多余文字)。"""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: s.rfind("```")]
        s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


class AnthropicProvider:
    """Claude Messages API + tool use(强制 emit_brief)。"""

    name = "anthropic"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, data_block: str, linkage_map: str) -> dict:
        body = _http_post_json(
            self.API_URL,
            {
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            {
                "model": self.model,
                "max_tokens": 4096,
                "system": SYSTEM,
                "tools": [
                    {
                        "name": "emit_brief",
                        "description": "输出四层结构的每日宏观简报",
                        "input_schema": BRIEF_SCHEMA,
                    }
                ],
                "tool_choice": {"type": "tool", "name": "emit_brief"},
                "messages": [{"role": "user", "content": build_user(data_block, linkage_map)}],
            },
        )
        for block in body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "emit_brief":
                return block["input"]
        raise RuntimeError("Anthropic 响应未包含 emit_brief 工具调用")


class OpenAICompatProvider:
    """OpenAI 兼容的 Chat Completions 端点 + function calling(失败回退解析 JSON)。"""

    def __init__(self, name: str, url: str, api_key: str, model: str):
        self.name = name
        self.url = url
        self.api_key = api_key
        self.model = model

    def generate(self, data_block: str, linkage_map: str) -> dict:
        body = _http_post_json(
            self.url,
            {
                "content-type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            },
            {
                "model": self.model,
                "max_tokens": 4096,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": build_user(data_block, linkage_map)},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "emit_brief",
                            "description": "输出四层结构的每日宏观简报",
                            "parameters": BRIEF_SCHEMA,
                        },
                    }
                ],
                "tool_choice": {"type": "function", "function": {"name": "emit_brief"}},
            },
        )
        msg = body["choices"][0]["message"]
        calls = msg.get("tool_calls")
        if calls:
            return json.loads(calls[0]["function"]["arguments"])
        # 回退:有的兼容端点不支持强制函数调用,直接把 JSON 写进 content。
        return _extract_json(msg.get("content") or "")


# 预设的 OpenAI 兼容端点。模型名可能随各家目录更新,用 <PREFIX>_MODEL 或 LLM_MODEL 覆盖。
# (url, key_env, model_env, default_model)
PRESETS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
    "minimax": ("https://api.minimax.chat/v1/text/chatcompletion_v2", "MINIMAX_API_KEY", "MINIMAX_MODEL", "abab6.5s-chat"),
    "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-chat"),
    "moonshot": ("https://api.moonshot.cn/v1/chat/completions", "MOONSHOT_API_KEY", "MOONSHOT_MODEL", "moonshot-v1-8k"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "ZHIPU_API_KEY", "ZHIPU_MODEL", "glm-4-flash"),
}

# 自动探测顺序(无 LLM_PROVIDER 时)。
_AUTO_ORDER = ["anthropic", "openai", "minimax", "deepseek", "moonshot", "zhipu", "openai-compat"]


def _build(name: str):
    """按名字构造 provider;对应 key 缺失则返回 None。"""
    if not name:
        return None
    if name == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        return AnthropicProvider(key, os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-6")
    if name in ("openai-compat", "generic", "custom"):
        key = os.environ.get("LLM_API_KEY")
        url = os.environ.get("LLM_BASE_URL")
        if not (key and url):
            return None
        return OpenAICompatProvider("openai-compat", url, key, os.environ.get("LLM_MODEL") or "gpt-4o-mini")
    if name in PRESETS:
        url, key_env, model_env, default_model = PRESETS[name]
        key = os.environ.get(key_env)
        if not key:
            return None
        model = os.environ.get(model_env) or os.environ.get("LLM_MODEL") or default_model
        return OpenAICompatProvider(name, url, key, model)
    return None


def select_provider():
    """根据 env 选 provider;LLM_PROVIDER 优先,否则按存在的 key 自动探测;都没有则 None。"""
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit:
        return _build(explicit)
    for name in _AUTO_ORDER:
        p = _build(name)
        if p:
            return p
    return None
