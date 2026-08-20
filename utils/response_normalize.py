"""utils/response_normalize.py — 平台 client 适配层。

平台注入的 client.chat 返回值形态不确定（可能是 str、OpenAI choices dict、
content blocks 数组、bytes 或带 content 属性的对象）。本模块在调用点统一
收口：任何返回值先归一化为纯文本，再进入图；并做签名探测以兼容多种
client 调用约定。
"""

from __future__ import annotations


def _blocks_text(blocks) -> str:
    """content blocks 数组 → 纯文本。兼容 str/bytes/dict/text 片段。"""
    if isinstance(blocks, str):
        return blocks
    if isinstance(blocks, bytes):
        try:
            return blocks.decode("utf-8", "ignore")
        except Exception:
            return ""
    if not isinstance(blocks, list):
        return ""
    parts = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, bytes):
            try:
                parts.append(block.decode("utf-8", "ignore"))
            except Exception:
                pass
        elif isinstance(block, dict):
            text = block.get("text") or block.get("content") or ""
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(text, bytes):
                try:
                    parts.append(text.decode("utf-8", "ignore"))
                except Exception:
                    pass
    return "".join(parts)


def normalize_chat_response(resp) -> str:
    """把任意形态的 client.chat 返回值归一化为纯文本。永不抛异常。"""
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, bytes):
        try:
            return resp.decode("utf-8", "ignore")
        except Exception:
            return ""
    if isinstance(resp, list):
        return _blocks_text(resp)
    if isinstance(resp, dict):
        # OpenAI 形态：choices[0].message.content
        try:
            choices = resp.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or choices[0]
                text = _blocks_text(message.get("content"))
                if text:
                    return text
        except Exception:
            pass
        # 其他常见键
        for key in ("content", "text", "answer"):
            text = _blocks_text(resp.get(key))
            if text.strip():
                return text
            value = resp.get(key)
            if isinstance(value, dict):
                nested = _blocks_text(value.get("content") or value.get("text"))
                if nested.strip():
                    return nested
        return ""
    # 对象形态（如 AgentMessage）：取 content 属性，兜底 str()
    content = getattr(resp, "content", None)
    text = _blocks_text(content)
    if text:
        return text
    try:
        return str(resp)
    except Exception:
        return ""


def detect_truncation(resp) -> bool:
    """检测返回值是否因 max_tokens 被截断（finish_reason == 'length'）。"""
    try:
        if isinstance(resp, dict):
            choices = resp.get("choices") or []
            if choices and isinstance(choices[0], dict):
                return choices[0].get("finish_reason") == "length"
            return resp.get("finish_reason") == "length"
        return getattr(resp, "finish_reason", None) == "length"
    except Exception:
        return False


def chat_compatible(client, messages, temperature, max_tokens, thinking_mode=None):
    """签名探测调用，兼容任意平台 client 的 chat 约定。

    按 关键字三参 → 位置三参 → 仅 messages 三级降级；探测结果缓存在
    client 对象上，避免每次调用都付一次 TypeError。
    """
    mode = getattr(client, "_agent_chat_mode", None)

    def _kwargs():
        kw = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if thinking_mode is not None:
            kw["thinking_mode"] = thinking_mode
        return client.chat(**kw)

    attempts = {
        "kwargs": _kwargs,
        "positional": lambda: client.chat(messages, temperature, max_tokens),
        "messages_only": lambda: client.chat(messages),
    }
    if mode in attempts:
        try:
            return attempts[mode]()
        except TypeError:
            pass  # 缓存失效，重新探测
    last_error = None
    for name in ("kwargs", "positional", "messages_only"):
        try:
            result = attempts[name]()
            try:
                setattr(client, "_agent_chat_mode", name)
            except Exception:
                pass
            return result
        except TypeError as exc:
            last_error = exc
            continue
    raise last_error
