"""nodes/playoff_node.py — 冲突复算裁决。

两路答案冲突时，投票只能"选"不能"算"（两个都错时必输）。
本节点把两个候选代回原题做确定性复算（方程残差/极值比较/小规模枚举），
用确定性证据裁决，替代采样判断。
"""

from __future__ import annotations

import re

from config import CONFIG
from nodes.python_agent_node import extract_code
from utils.answer_matcher import is_placeholder_answer
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, thinking_mode_flag
from utils.prompt_templates import PLAYOFF_PROMPT, PLAYOFF_PREFILL

_RESULT_RE = re.compile(r"PLAYOFF_RESULT[：:]\s*(BOTH|NEITHER|INCONCLUSIVE|A|B)\b", re.IGNORECASE)


def _bounded(value, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[截断]"


def _usable(value) -> str:
    text = str(value or "").strip()
    return "" if is_placeholder_answer(text) else text


def playoff_node(state: dict, config) -> dict:
    trace = list(state.get("playoff_trace") or [])
    if not CONFIG.get("enable_playoff", True):
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    deps = get_deps(config)
    rr = _usable((state.get("reasoning_result") or {}).get("answer"))
    po = _usable((state.get("python_output") or {}).get("answer"))
    candidate_a, candidate_b = rr, po
    if not candidate_a or not candidate_b:
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    clock = deps.time_budget
    if clock and clock.remaining_hard() - CONFIG.get("compressed_reserve_margin_s", 150) \
            < 150 + CONFIG["node_timeouts"]["python_execute"]:
        return {"playoff_status": "skipped", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    prompt = PLAYOFF_PROMPT.format(
        problem=_bounded(state.get("problem", ""), 8000),
        candidate_a=_bounded(candidate_a, 2500),
        candidate_b=_bounded(candidate_b, 2500))
    try:
        resp = chat_prefilled(
            deps.client, messages=[{"role": "user", "content": prompt}],
            prefix=PLAYOFF_PREFILL,
            temperature=CONFIG["temperatures"]["python"],
            max_tokens=CONFIG["max_tokens"]["python_compressed"],
            logger=deps.logger, time_budget=clock,
            expected_call_seconds=150, label="playoff_generate",
            reserve_margin_s=CONFIG.get("compressed_reserve_margin_s", 150),
            thinking_mode=thinking_mode_flag(),
        )
    except Exception as exc:  # noqa: BLE001
        trace.append({"status": "error", "reason": str(exc)[:200]})
        return {"playoff_status": "error", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    code = extract_code(resp)
    if not code:
        return {"playoff_status": "indecisive", "playoff_trace": trace,
                "next_node": "semantic_arbiter"}

    from utils.python_executor import PythonExecutor
    output = PythonExecutor(timeout=CONFIG["node_timeouts"]["python_execute"]).execute(code)
    stdout = str(output.get("stdout") or "")
    matches = _RESULT_RE.findall(stdout)
    verdict = matches[-1].upper() if matches else "INCONCLUSIVE"

    if verdict in ("A", "B", "BOTH"):
        if verdict == "A":
            chosen = candidate_a
        elif verdict == "B":
            chosen = candidate_b
        else:
            chosen = candidate_a if len(candidate_a) <= len(candidate_b) else candidate_b
        return {
            "playoff_status": "decisive", "playoff_trace": trace,
            "validated_answer": chosen, "next_node": "critic",
        }
    if verdict == "NEITHER":
        hint = ("两个候选答案经独立复算均未通过核验。两者都不可信，"
                "请彻底更换解题方法重新独立求解，并用代码验证新结论。")
        return {
            "playoff_status": "neither", "playoff_trace": trace,
            "reasoning_retry_hint": hint, "python_retry_hint": hint,
            "next_node": "reconciliation",
        }
    return {"playoff_status": "indecisive", "playoff_trace": trace,
            "next_node": "semantic_arbiter"}
