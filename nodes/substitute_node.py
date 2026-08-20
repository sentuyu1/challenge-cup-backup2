"""nodes/substitute_node.py — 单候选代回核验。

交叉验证 match 只保证"推理与 Python 两路一致"，但两路同源（同一模型、
同一题面读法）可能一致地错。本节点把候选答案代回题面条件做确定性核验
（方程验残差/极值代回比较/计数小规模枚举），戳穿"同源同错"。
"""

from __future__ import annotations

import re

from config import CONFIG
from nodes.python_agent_node import extract_code
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, thinking_mode_flag
from utils.prompt_templates import SUBSTITUTE_PROMPT, SUBSTITUTE_PREFILL

_VERDICT_RE = re.compile(r"核验结果\s*[:：]\s*(PASS|FAIL|INCONCLUSIVE)", re.IGNORECASE)


def _bounded(value, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[截断]"


def substitute_node(state: dict, config) -> dict:
    trace = list(state.get("substitution_trace") or [])
    if not CONFIG.get("enable_substitution_check", True):
        return {"substitution_status": "skipped", "next_node": "critic"}

    deps = get_deps(config)
    answer = str(state.get("validated_answer") or "").strip()
    if not answer:
        return {"substitution_status": "skipped",
                "substitution_trace": trace, "next_node": "critic"}

    # 预算闸门：硬上限前必须容得下生成 + 执行 + 收尾
    clock = deps.time_budget
    if clock and clock.remaining_hard() - CONFIG.get("compressed_reserve_margin_s", 150) \
            < 150 + CONFIG["node_timeouts"]["python_execute"]:
        return {"substitution_status": "skipped",
                "substitution_trace": trace, "next_node": "critic"}

    prompt = SUBSTITUTE_PROMPT.format(
        problem=_bounded(state.get("problem", ""), 8000),
        answer=_bounded(answer, 2500))
    try:
        resp = chat_prefilled(
            deps.client, messages=[{"role": "user", "content": prompt}],
            prefix=SUBSTITUTE_PREFILL,
            temperature=CONFIG["temperatures"]["python"],
            max_tokens=CONFIG["max_tokens"]["python_compressed"],
            logger=deps.logger, time_budget=clock,
            expected_call_seconds=150, label="substitute_generate",
            reserve_margin_s=CONFIG.get("compressed_reserve_margin_s", 150),
            thinking_mode=thinking_mode_flag(),
        )
    except Exception as exc:  # noqa: BLE001
        trace.append({"status": "error", "reason": str(exc)[:200]})
        return {"substitution_status": "error", "substitution_trace": trace,
                "next_node": "critic"}

    code = extract_code(resp)
    if not code:
        trace.append({"status": "indecisive", "reason": "no_code"})
        return {"substitution_status": "indecisive", "substitution_trace": trace,
                "next_node": "critic"}

    from utils.python_executor import PythonExecutor
    output = PythonExecutor(timeout=CONFIG["node_timeouts"]["python_execute"]).execute(code)
    stdout = str(output.get("stdout") or "")
    m = _VERDICT_RE.search(stdout)
    verdict = m.group(1).upper() if m else "INCONCLUSIVE"

    if verdict == "FAIL":
        hint = ("候选答案经独立代回核验未通过（FAIL）。此前一致结论已被确定性计算证伪，"
                "请彻底更换解题方法重新独立推导，逐项复核题面条件，并用代码验证新结论。")
        return {
            "substitution_status": "fail", "substitution_trace": trace,
            "reasoning_retry_hint": hint,
            "python_retry_hint": hint + "\n请用代码独立验证新结论。",
            "next_node": "reconciliation",
        }
    return {"substitution_status": "pass" if verdict == "PASS" else "indecisive",
            "substitution_trace": trace, "next_node": "critic"}
