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
    start = s.find("{")
    if start != -1:
        obj, _ = json.JSONDecoder().raw_decode(s[start:])  # 只取第一个对象,容忍尾部多余
        return obj
    return json.loads(s)


def _extract_tool_input(body: dict, tool_name: str) -> dict | None:
    """从 Anthropic(或中转站)响应里抠出工具入参,多路兜底:
    ① 原生 tool_use 块;② 中转站加的 OpenAI 风格 tool_calls;③ 模型把 JSON 当文本吐(```json ...```)。
    中转站的 Claude 在复杂 schema 下不稳定(有时只回文本),靠这三路 + 上层重试稳住。都拿不到则 None。
    """
    for block in body.get("content", []) or []:
        if block.get("type") == "tool_use" and block.get("name") == tool_name:
            inp = block.get("input")
            if isinstance(inp, dict) and inp:
                return inp
    for tc in body.get("tool_calls", []) or []:
        args = (tc.get("function") or {}).get("arguments")
        if isinstance(args, dict) and args:
            return args
        if isinstance(args, str) and args.strip():
            try:
                return _extract_json(args)
            except (json.JSONDecodeError, ValueError):
                pass
    texts = "".join(b.get("text", "") for b in body.get("content", []) or [] if b.get("type") == "text")
    if texts.strip():
        try:
            return _extract_json(texts)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


class AnthropicProvider:
    """Claude Messages API + tool use(强制工具调用)。支持自定义 base_url(中转站)。"""

    name = "anthropic"
    DEFAULT_BASE = "https://api.anthropic.com"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.url = (base_url or self.DEFAULT_BASE).rstrip("/") + "/v1/messages"

    def call_structured(
        self, system: str, user: str, tool_name: str, description: str, schema: dict
    ) -> dict:
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            # 官方端点认 x-api-key;中转站多认 Authorization: Bearer——两者都带,互不干扰。
            "x-api-key": self.api_key,
            "authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": system,
            "tools": [{"name": tool_name, "description": description, "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": tool_name},
            "messages": [{"role": "user", "content": user}],
        }
        last = ""
        for _ in range(3):  # 中转站 Claude 偶发只回文本/不回 tool_use → 多路兜底 + 重试
            body = _http_post_json(self.url, headers, payload)
            data = _extract_tool_input(body, tool_name)
            if data is not None:
                return data
            last = str(body)[:200]
        raise RuntimeError(f"Anthropic 未返回可解析的 {tool_name} 结构: {last}")


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
        # 用 JSON mode(response_format)而非强制 function-calling:后者在复杂 schema 下
        # 结构性失稳(DeepSeek 会在大数组后提前闭合根对象、把后续字段当兄弟对象续写);
        # JSON mode + 把 schema 写进 system(需含 "JSON" 字样)更稳。返回正文里的 JSON。
        headers = {"content-type": "application/json", "authorization": f"Bearer {self.api_key}"}
        sys = (
            system
            + "\n\n【输出】只返回一个 JSON 对象,不要 markdown 围栏、不要多余文字;"
            + "严格符合下面的 JSON Schema(键名 / 枚举 / 必填项):\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
        }
        last_err: Exception | None = None
        for _ in range(3):  # 偶发非法 JSON(未转义引号等)→ 重试,非零温度二次大概率合法
            body = _http_post_json(self.url, headers, payload)
            base = body.get("base_resp")  # MiniMax 等把错误塞在 HTTP 200 的 base_resp
            if isinstance(base, dict) and base.get("status_code") not in (0, None):
                raise RuntimeError(f"{self.name} 返回错误: {base}")
            choices = body.get("choices")
            if not choices:
                raise RuntimeError(f"{self.name} 响应无 choices: {str(body)[:200]}")
            content = choices[0].get("message", {}).get("content") or ""
            try:
                return _extract_json(content)
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


def _compat_url(override: str | None, default_full: str) -> str:
    """把 *_BASE_URL 归一成完整端点:已含路径则原样;只给 host(中转站常见)则补 /v1/chat/completions。"""
    if not override:
        return default_full
    ov = override.rstrip("/")
    return ov if ("/chat/completions" in ov or "/responses" in ov or "/completions" in ov) else ov + "/v1/chat/completions"


def _build(name: str):
    if not name:
        return None
    if name == "anthropic":
        # 中转站用 ANTHROPIC_AUTH_TOKEN(Bearer),官方用 ANTHROPIC_API_KEY(x-api-key);两者择一即可。
        key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return None
        base = os.environ.get("ANTHROPIC_BASE_URL")
        model = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-6"
        return AnthropicProvider(key, model, base)
    if name in ("openai-compat", "generic", "custom"):
        key, url = os.environ.get("LLM_API_KEY"), os.environ.get("LLM_BASE_URL")
        return OpenAICompatProvider("openai-compat", _compat_url(url, url or ""), key, os.environ.get("LLM_MODEL") or "gpt-4o-mini") if (key and url) else None
    if name in PRESETS:
        url, key_env, model_env, default_model = PRESETS[name]
        key = os.environ.get(key_env)
        if not key:
            return None
        url = _compat_url(os.environ.get(f"{name.upper()}_BASE_URL"), url)
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


def select_providers() -> list:
    """多模型 provider 列表:`LLM_MODELS=deepseek,anthropic`(逗号分隔,顺序即视图顺序,[0]=主模型);
    未设则回退单 provider(= `select_provider()`,保持现状)。缺 key 的自动跳过,按 name 去重。"""
    raw = (os.environ.get("LLM_MODELS") or "").strip()
    if not raw:
        p = select_provider()
        return [p] if p else []
    out, seen = [], set()
    for name in (n.strip().lower() for n in raw.split(",")):
        if not name or name in seen:
            continue
        p = _build(name)
        if p:
            out.append(p)
            seen.add(name)
    return out
