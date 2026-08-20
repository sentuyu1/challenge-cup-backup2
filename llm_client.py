"""llm_client.py — 本地调试用的 OpenAI 兼容 Chat 客户端。

平台评测时注入官方 client（不经此文件）；本地调试时用此客户端直连
Intern-S API。读环境变量 INTERN_API_KEY / INTERN_MODEL。
"""

from __future__ import annotations

import json
import os
import time

import requests

DEFAULT_API_BASE = "https://chat.intern-ai.org.cn/api/v1/chat/completions"
DEFAULT_MODEL = "intern-s2-preview-397b"


class InternChatClient:
    """OpenAI 兼容 Chat 客户端（本地调试）。"""

    def __init__(self, timeout: int = 120, retry: int = 2):
        raw_key = os.environ.get("INTERN_API_KEY")
        if not raw_key:
            raise RuntimeError("缺少 API key，请设置 INTERN_API_KEY 环境变量")
        self.authorization = raw_key if raw_key.startswith("Bearer ") else f"Bearer {raw_key}"
        self.api_base = os.environ.get("INTERN_API_BASE", DEFAULT_API_BASE)
        self.model = os.environ.get("INTERN_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.retry = retry

    def chat(self, messages, temperature=0.2, max_tokens=4096, thinking_mode=None) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if thinking_mode is not None:
            payload["thinking_mode"] = thinking_mode
        headers = {"Content-Type": "application/json", "Authorization": self.authorization}

        last_error = None
        for attempt in range(self.retry):
            try:
                resp = requests.post(
                    self.api_base, headers=headers,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt + 1 < self.retry:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"Chat 调用失败（{self.retry} 次重试后）: {last_error}")
