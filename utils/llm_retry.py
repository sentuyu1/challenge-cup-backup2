"""utils/llm_retry.py — LLM 调用层（重试 + prefill + 截断续写）。

重试按「deadline 定价」而非固定次数：上一次调用实测耗时是多少，就按那个
耗时间预算买不买得起下一次重试。平台注入的 client 内部可能自带重试，
外层再叠固定次数会失控（单节点烧掉 9 次请求 ≈ 1080s）。
"""

from __future__ import annotations

import re
import time

from config import CONFIG
from utils.prefill import prefill_messages, stitch
from utils.response_normalize import (
    chat_compatible, detect_truncation, normalize_chat_response)


class DeadlineExceeded(RuntimeError):
    """时间预算无法再购买一次调用。"""


def thinking_mode_flag():
    """关 CoT：官方原生 thinking_mode=False；不传 = 保持默认深度思考。"""
    return False if CONFIG.get("enable_thinking_mode_off") else None


class LLMRetryWrapper:
    def __init__(
        self, client, max_retries=2, backoff_factor=1.5, logger=None,
        time_budget=None, expected_call_seconds=None, reserve_margin_s=None,
    ):
        self.client = client
        self.max_retries = max(1, max_retries)
        self.backoff_factor = backoff_factor
        self.logger = logger
        self.time_budget = time_budget
        self.expected_call_seconds = expected_call_seconds
        self.reserve_margin_s = reserve_margin_s

    def _now(self) -> float:
        if self.time_budget is not None:
            return self.time_budget.now()
        return time.monotonic()

    def _affordable(self, observed=None) -> bool:
        if self.time_budget is None:
            return True
        estimate = self.expected_call_seconds
        if observed is not None:
            estimate = observed if estimate is None else max(estimate, observed)
        if self.reserve_margin_s is not None:
            window = self.time_budget.remaining_hard() - float(self.reserve_margin_s)
            return window >= (estimate if estimate is not None else 1.0)
        if estimate is None:
            return not self.time_budget.expired()
        return self.time_budget.can_afford(estimate)

    def chat(self, messages, temperature=0.2, max_tokens=4096,
             label="llm", thinking_mode=None) -> str:
        if not self._affordable():
            raise DeadlineExceeded(f"{label}: 预算不足")
        # 单题请求硬上限（emergency 豁免）
        cap_check = getattr(self.time_budget, "llm_calls_exhausted", None)
        if (self.time_budget is not None and label != "emergency_answer"
                and callable(cap_check) and cap_check()):
            raise DeadlineExceeded(f"{label}: 请求数已达上限")
        bump = getattr(self.time_budget, "bump_llm_call", None)
        if callable(bump):
            bump()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            started = self._now()
            try:
                raw = chat_compatible(
                    self.client, messages, temperature, max_tokens, thinking_mode)
                result = normalize_chat_response(raw)
                if self.time_budget is not None:
                    self.time_budget.record(label, self._now() - started)
                # 截断续写：finish_reason=length 或启发式判定未写完时续写补全
                if result and result.strip():
                    if detect_truncation(raw) or (
                            not _finish_reason_visible(raw)
                            and _looks_truncated(result, max_tokens)):
                        result = self._continue_truncated(
                            messages, result, temperature, label, thinking_mode)
                return result
            except Exception as exc:  # 传输失败重试
                last_error = exc
                observed = self._now() - started
                if self.time_budget is not None:
                    self.time_budget.record(f"{label}:failed", observed)
                if attempt >= self.max_retries:
                    break
                if not self._affordable(observed):
                    break
                delay = self.backoff_factor ** (attempt - 1)
                err_text = f"{exc}".lower()
                if any(k in err_text for k in ("429", "rate limit", "rate_limit",
                                               "配额", "quota", "-20081", "busy",
                                               "overloaded", "too many")):
                    delay = max(delay, 10.0 + 5.0 * attempt)
                if delay > 0:
                    time.sleep(delay)
        raise last_error

    def _continue_truncated(self, messages, result, temperature, label, thinking_mode):
        """finish_reason=length 时，用结尾片段 prefill 续写补全（至多 1 轮）。"""
        current = result
        try:
            if self.time_budget is not None:
                if self.time_budget.remaining_hard() < 105:
                    return current
                if not self._affordable():
                    return current
            tail = current[-120:] if len(current) > 120 else current
            raw2 = chat_compatible(
                self.client, prefill_messages(messages, tail),
                temperature, 4096, thinking_mode)
            completion = normalize_chat_response(raw2)
            if not completion or not completion.strip():
                return current
            stitched = stitch(tail, completion)
            if stitched and stitched != tail:
                current = (current + stitched[len(tail):]
                           if stitched.startswith(tail) else current + stitched)
        except Exception:
            pass
        return current


def _finish_reason_visible(resp) -> bool:
    try:
        if isinstance(resp, dict):
            choices = resp.get("choices") or []
            if choices and isinstance(choices[0], dict):
                return "finish_reason" in choices[0]
            return "finish_reason" in resp
        return hasattr(resp, "finish_reason")
    except Exception:
        return True


def _looks_truncated(text: str, max_tokens: int) -> bool:
    """finish_reason 不可见时的截断启发式。"""
    if not isinstance(text, str) or max_tokens <= 0:
        return False
    s = text.rstrip()
    # 强信号：未闭合 LaTeX / 命令残片
    if s.count("$") % 2 == 1:
        return True
    if s.count("{") > s.count("}"):
        return True
    if re.search(r"\\[a-zA-Z]+$", s):
        return True
    effective_cap = min(int(max_tokens), 4096)
    if len(s) < effective_cap * 1.2:
        return False
    tail = s[-60:]
    return bool(re.search(r"[-:：,，、=＝]\s*$|\\[a-zA-Z]*$|^\s*(?:\d+[.、)]|[-*•])\s*$", tail))


def chat_with_retry(client, messages, temperature=0.2, max_tokens=4096,
                    logger=None, time_budget=None, expected_call_seconds=None,
                    label="llm", thinking_mode=None):
    return LLMRetryWrapper(
        client, max_retries=CONFIG["llm_max_retries"],
        backoff_factor=CONFIG["backoff_factor"], logger=logger,
        time_budget=time_budget, expected_call_seconds=expected_call_seconds,
    ).chat(messages=messages, temperature=temperature, max_tokens=max_tokens,
           label=label, thinking_mode=thinking_mode)


def chat_prefilled(client, messages, prefix, temperature=0.1, max_tokens=256,
                   logger=None, time_budget=None, expected_call_seconds=None,
                   label="llm_prefill", reserve_margin_s=None, thinking_mode=None):
    """一次 prefill 往返，返回拼接后的 assistant 文本。"""
    wrapper = LLMRetryWrapper(
        client, max_retries=1, backoff_factor=CONFIG["backoff_factor"],
        logger=logger, time_budget=time_budget,
        expected_call_seconds=expected_call_seconds, reserve_margin_s=reserve_margin_s,
    )
    raw = wrapper.chat(
        messages=prefill_messages(messages, prefix),
        temperature=temperature, max_tokens=max_tokens, label=label,
        thinking_mode=thinking_mode)
    return stitch(prefix, raw)
