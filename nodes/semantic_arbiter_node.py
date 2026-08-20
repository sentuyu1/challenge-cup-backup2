"""nodes/semantic_arbiter_node.py — 语义仲裁。

两路答案不确定/冲突且无法确定性裁决时，从既有候选中选一个或弃权。
只选不生成，prefill 调用（~1s），避免再付一次完整推理。
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.answer_matcher import is_placeholder_answer
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, thinking_mode_flag
from utils.prompt_templates import SEMANTIC_ARBITER_PROMPT, SEMANTIC_ARBITER_PREFILL


def _usable(value) -> str:
    text = str(value or "").strip()
    return "" if is_placeholder_answer(text) else text


def semantic_arbiter_node(state: dict, config) -> dict:
    trace = list(state.get("semantic_arbiter_trace") or [])
    deps = get_deps(config)

    candidate_a = _usable((state.get("reasoning_result") or {}).get("answer"))
    candidate_b = _usable((state.get("python_output") or {}).get("answer"))

    # 候选不足两个：只有一个可用则直接采用，都没有则弃权
    if not candidate_a and not candidate_b:
        return {"semantic_arbiter_status": "abstained", "semantic_arbiter_trace": trace,
                "next_node": "coordinator"}
    if candidate_a and not candidate_b:
        return {"semantic_arbiter_status": "selected", "validated_answer": candidate_a,
                "semantic_arbiter_trace": trace, "answer_locked": True,
                "next_node": "coordinator"}
    if candidate_b and not candidate_a:
        return {"semantic_arbiter_status": "selected", "validated_answer": candidate_b,
                "semantic_arbiter_trace": trace, "answer_locked": True,
                "next_node": "coordinator"}

    prompt = SEMANTIC_ARBITER_PROMPT.format(
        problem=str(state.get("problem", ""))[:6000],
        candidate_a=candidate_a[:2500], candidate_b=candidate_b[:2500])
    try:
        raw = chat_prefilled(
            deps.client, messages=[{"role": "user", "content": prompt}],
            prefix=SEMANTIC_ARBITER_PREFILL, temperature=0.1, max_tokens=256,
            logger=deps.logger, time_budget=deps.time_budget,
            expected_call_seconds=15, label="semantic_arbiter_prefill",
            reserve_margin_s=CONFIG.get("arbiter_reserve_quota_s", 75),
            thinking_mode=thinking_mode_flag(),
        )
    except Exception:  # noqa: BLE001 - 仲裁失败回退到推理候选
        return {"semantic_arbiter_status": "abstained",
                "validated_answer": candidate_a,
                "semantic_arbiter_trace": trace, "answer_locked": True,
                "next_node": "coordinator"}

    m = re.search(r"SELECT\s*[:：]\s*([AB])\b", raw, re.IGNORECASE)
    if m:
        chosen = candidate_a if m.group(1).upper() == "A" else candidate_b
        trace.append({"decision": m.group(1).upper()})
        return {"semantic_arbiter_status": "selected", "validated_answer": chosen,
                "semantic_arbiter_trace": trace, "answer_locked": True,
                "next_node": "coordinator"}

    # 弃权：回退到推理候选（可读性更好）
    return {"semantic_arbiter_status": "abstained", "validated_answer": candidate_a,
            "semantic_arbiter_trace": trace, "answer_locked": True,
            "next_node": "coordinator"}
