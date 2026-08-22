"""utils/answer_render.py — answer_frame 答案渲染（折叠桌 _render_answer 思想）。

把「裸数值答案」渲染成「完整可读句子」，满足官方 FAQ「清晰可独立判分」的要求：
  计数题 16 → 所求数量为16个。
  概率题 1/2 → 所求概率为1/2。
  判断题 是 → 是。
纯规则，零 LLM 成本。
"""

from __future__ import annotations

import re


def _as_sentence(value: str) -> str:
    v = str(value or "").strip()
    return v if v.endswith(("。", "！", "？", ".", "!", "?")) else f"{v}。"


def _last_scalar(value: str) -> str:
    numbers = re.findall(r"[+-]?(?:\d+(?:/\d+)?|\d*\.\d+)", value)
    return numbers[-1] if numbers else ""


def render_answer(answer: str, question_kind: str, unit: str = "个") -> str:
    """把裸答案渲染成句子（sentence 类答案）。"""
    value = str(answer or "").strip()
    if not value:
        return value
    if question_kind == "count":
        if unit in value:
            return _as_sentence(value)
        scalar = _last_scalar(value)
        if scalar and scalar == value:
            return _as_sentence(f"所求数量为{value}{unit}")
        return _as_sentence(value)
    if question_kind == "probability":
        if "概率" in value:
            return _as_sentence(value)
        scalar = _last_scalar(value)
        if scalar and scalar == value:
            return _as_sentence(f"所求概率为{value}")
        return _as_sentence(value)
    if question_kind == "truth":
        compact = re.sub(r"[\s。.]", "", value)
        normalized = {
            "是": "是", "正确": "是", "成立": "是", "可以": "可以",
            "否": "否", "错误": "否", "不成立": "否", "不可以": "不可以",
        }
        judgement = normalized.get(compact, value)
        return _as_sentence(judgement)
    return value
