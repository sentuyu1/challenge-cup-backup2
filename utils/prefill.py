"""utils/prefill.py — assistant 预填充（跳过 CoT 的关键杠杆）。

原理：在 messages 末尾追加一条 assistant 消息作为「种子」，让模型进入
续写模式而非从零推理，从而不打开 reasoning_content（私有 CoT）块。
实测可把分类/仲裁等判断类调用从 ~40s 降到 ~1s。

兼容性：只追加一条 assistant 消息，因此通过平台注入的
client.chat(messages=...) 即可工作，无需改 client。不同后端对末尾
assistant 轮的处理不同（续写 / 回显 / 忽略），故 stitch 兼容三种形态，
调用方始终保留非 prefill 的兜底路径。
"""

from __future__ import annotations


def prefill_messages(messages: list, prefix: str) -> list:
    """在消息末尾追加 assistant 种子轮。"""
    return list(messages) + [{"role": "assistant", "content": prefix}]


def stitch(prefix: str, completion: str) -> str:
    """把种子与返回内容拼回完整 assistant 文本。

    处理三种后端行为：
      * continuation — completion 紧接 prefix 之后继续 → 直接拼接
      * echo         — completion 已回显 prefix → 原样使用
      * ignored      — completion 是独立完整答案 → 原样使用
    """
    body = completion if isinstance(completion, str) else str(completion or "")
    seed = prefix if isinstance(prefix, str) else str(prefix or "")
    if not seed:
        return body
    stripped = body.lstrip()
    if stripped.startswith(seed):
        return stripped
    # 回显带前导包装（换行/代码围栏等）
    head = body[: len(seed) + 40]
    if seed in head:
        return body[body.index(seed):]
    return seed + body
