"""飞书(Lark)自定义机器人 webhook 推送(纯标准库)。

环境变量:
- FEISHU_WEBHOOK :机器人 webhook 地址(必需才推送;缺失则跳过——本地 md 即兜底)
- FEISHU_SECRET  :可选,机器人开启「签名校验」时填入

文档:https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request


def _sign(timestamp: int, secret: str) -> str:
    """飞书签名:HMAC-SHA256,以 "{timestamp}\\n{secret}" 为 key、空串为消息,再 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def push_text(text: str) -> bool:
    """把文本推到飞书机器人。未配置 FEISHU_WEBHOOK 时返回 False(未推送)。

    成功返回 True;飞书返回非零业务码时抛 RuntimeError。
    """
    webhook = os.environ.get("FEISHU_WEBHOOK")
    if not webhook:
        return False

    body: dict = {"msg_type": "text", "content": {"text": text}}
    secret = os.environ.get("FEISHU_SECRET")
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = _sign(ts, secret)

    req = urllib.request.Request(
        webhook,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read().decode("utf-8"))

    # 成功:{"code":0,...}(新)或 {"StatusCode":0,...}(旧)。
    code = out.get("code", out.get("StatusCode", -1))
    if code != 0:
        raise RuntimeError(f"飞书推送失败: {out}")
    return True
