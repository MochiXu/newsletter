"""多模型 provider 抽象:把「结构化输出」统一成一个接口,可换底层大模型。

支持 anthropic(tool use)与 OpenAI 兼容端点(function calling,失败回退解析 JSON):
openai / minimax / deepseek / moonshot / zhipu / 通用 openai-compat。

选择(env):`LLM_PROVIDER` 显式;缺省按存在的 key 自动探测。纯标准库(urllib)。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{url.split('?', 1)[0]} 返回 {e.code}: {detail}") from None


def _extract_json(text: str) -> dict:
    """从模型文本里抠出 JSON 对象(容忍 ```json 围栏与前后多余文字)。"""
    s = (text or "").strip()
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
    """Claude Messages API + tool use(强制工具调用)。"""

    name = "anthropic"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def call_structured(
        self, system: str, user: str, tool_name: str, description: str, schema: dict
    ) -> dict:
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
                "system": system,
                "tools": [{"name": tool_name, "description": description, "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": tool_name},
                "messages": [{"role": "user", "content": user}],
            },
        )
        for block in body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                return block["input"]
        raise RuntimeError(f"Anthropic 响应未包含 {tool_name} 工具调用")


class OpenAICompatProvider:
    """OpenAI 兼容 Chat Completions + function calling(失败回退解析 JSON)。"""

    def __init__(self, name: str, url: str, api_key: str, model: str):
        self.name = name
        self.url = url
        self.api_key = api_key
        self.model = model

    def call_structured(
        self, system: str, user: str, tool_name: str, description: str, schema: dict
    ) -> dict:
        headers = {"content-type": "application/json", "authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": tool_name, "description": description, "parameters": schema},
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": tool_name}},
        }
        # LLM 偶发非法 JSON(如字符串内未转义引号)→ 重试一次(非零温度,二次大概率合法)。
        last_err: Exception | None = None
        for _ in range(2):
            body = _http_post_json(self.url, headers, payload)
            base = body.get("base_resp")  # MiniMax 等把错误塞在 HTTP 200 的 base_resp
            if isinstance(base, dict) and base.get("status_code") not in (0, None):
                raise RuntimeError(f"{self.name} 返回错误: {base}")
            choices = body.get("choices")
            if not choices:
                raise RuntimeError(f"{self.name} 响应无 choices: {str(body)[:200]}")
            msg = choices[0].get("message", {})
            calls = msg.get("tool_calls")
            raw = calls[0]["function"]["arguments"] if calls else (msg.get("content") or "")
            try:
                return json.loads(raw) if calls else _extract_json(raw)
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
        raise RuntimeError(f"{self.name} 结构化输出 JSON 解析失败(已重试): {last_err}")


# 预设 OpenAI 兼容端点:(url, key_env, model_env, default_model)。模型名会随各家目录更新。
PRESETS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
    "minimax": ("https://api.minimaxi.com/v1/text/chatcompletion_v2", "MINIMAX_API_KEY", "MINIMAX_MODEL", "MiniMax-M2"),
    "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "deepseek-chat"),
    "moonshot": ("https://api.moonshot.cn/v1/chat/completions", "MOONSHOT_API_KEY", "MOONSHOT_MODEL", "moonshot-v1-8k"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "ZHIPU_API_KEY", "ZHIPU_MODEL", "glm-4-flash"),
}

_AUTO_ORDER = ["anthropic", "openai", "minimax", "deepseek", "moonshot", "zhipu", "openai-compat"]


def _build(name: str):
    if not name:
        return None
    if name == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        return AnthropicProvider(key, os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-6") if key else None
    if name in ("openai-compat", "generic", "custom"):
        key, url = os.environ.get("LLM_API_KEY"), os.environ.get("LLM_BASE_URL")
        return OpenAICompatProvider("openai-compat", url, key, os.environ.get("LLM_MODEL") or "gpt-4o-mini") if (key and url) else None
    if name in PRESETS:
        url, key_env, model_env, default_model = PRESETS[name]
        key = os.environ.get(key_env)
        if not key:
            return None
        url = os.environ.get(f"{name.upper()}_BASE_URL") or url
        model = os.environ.get(model_env) or os.environ.get("LLM_MODEL") or default_model
        return OpenAICompatProvider(name, url, key, model)
    return None


def select_provider():
    """LLM_PROVIDER 优先,否则按存在的 key 自动探测;都没有则 None。"""
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit:
        return _build(explicit)
    for name in _AUTO_ORDER:
        p = _build(name)
        if p:
            return p
    return None
