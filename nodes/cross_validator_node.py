"""nodes/cross_validator_node.py — 交叉验证。

对比 LLM 推理答案与 Python 计算答案，判断是否一致，决定下一跳：
  - match     → coordinator（或先 substitute 代回核验）
  - mismatch   → reconciliation（重试）或 semantic_arbiter（仲裁）
  - uncertain → semantic_arbiter
"""

from __future__ import annotations

from utils.answer_matcher import is_placeholder_answer, match_computation
from utils.deps import get_deps


def _clean(answer: str) -> str:
    return "" if is_placeholder_answer(answer) else (answer or "").strip()


def _preferred_answer(state: dict, is_match: bool, problem_type: str) -> str:
    """选出 validated_answer。

    证据优先：Python 确定性计算结果（sympy）优先于 LLM 散文；但 Python
    未真正验证或答案为空时回退到推理答案。
    """
    rr = state.get("reasoning_result") or {}
    po = state.get("python_output") or {}
    python_answer = _clean(po.get("answer", ""))
    reasoning_answer = _clean(rr.get("answer", ""))
    python_ok = bool(po.get("success")) and bool(python_answer)

    if problem_type == "proof":
        return reasoning_answer or python_answer

    # 计算题：Python 确定性成功且答案完整 → Python 优先
    if python_ok and not is_placeholder_answer(python_answer):
        # 两路一致：保留可读性更好的推理答案
        if is_match and reasoning_answer:
            return reasoning_answer
        return python_answer
    return reasoning_answer or python_answer


def cross_validator_node(state: dict, config) -> dict:
    deps = get_deps(config)
    rr = state.get("reasoning_result") or {}
    po = state.get("python_output") or {}
    question_mode = state.get("question_mode", "computation")

    reasoning_answer = _clean(rr.get("answer", ""))
    python_answer = _clean(po.get("answer", ""))

    # ── 客观题：只有推理路，直接采用 ──
    if question_mode in ("choice", "true_false", "fill"):
        if reasoning_answer:
            return {
                "validation_status": "match",
                "validated_answer": reasoning_answer,
                "validation_details": {"problem_type": question_mode,
                                       "reason": "客观题快速路径", "method": "objective"},
                "next_node": "coordinator",
            }
        return {
            "validation_status": "uncertain",
            "validated_answer": "",
            "validation_details": {"problem_type": question_mode,
                                   "reason": "客观题未提取到答案"},
            "next_node": "semantic_arbiter",
        }

    # ── 证明题：看推理完整性 ──
    if question_mode == "proof":
        complete = bool(rr.get("steps")) and len(rr.get("steps", [])) >= 2 \
            and bool(reasoning_answer) and len(reasoning_answer) > 10
        if complete:
            return {
                "validation_status": "match",
                "validated_answer": reasoning_answer,
                "validation_details": {"problem_type": "proof",
                                       "reason": "推理完整", "method": "proof"},
                "next_node": "coordinator",
            }
        return {
            "validation_status": "uncertain",
            "validated_answer": reasoning_answer,
            "validation_details": {"problem_type": "proof",
                                   "reason": "推理不完整"},
            "next_node": "semantic_arbiter",
        }

    # ── 计算题：符号等价匹配 ──
    if not reasoning_answer and not python_answer:
        return {
            "validation_status": "uncertain",
            "validated_answer": "",
            "validation_details": {"problem_type": "computation",
                                   "reason": "两路都无答案"},
            "next_node": "semantic_arbiter",
        }

    if reasoning_answer and python_answer:
        is_match, confidence, reason, method = match_computation(
            reasoning_answer, python_answer)
        if is_match and confidence >= 0.8:
            return {
                "validation_status": "match",
                "validated_answer": _preferred_answer(state, True, "computation"),
                "validation_details": {"problem_type": "computation",
                                       "reason": reason, "method": method,
                                       "confidence": confidence},
                "next_node": "coordinator",
            }
        if not is_match and confidence >= 0.7:
            return {
                "validation_status": "mismatch",
                "validated_answer": "",
                "validation_details": {"problem_type": "computation",
                                       "reason": reason, "method": method,
                                       "confidence": confidence},
                "next_node": "reconciliation",
            }
        return {
            "validation_status": "uncertain",
            "validated_answer": "",
            "validation_details": {"problem_type": "computation",
                                   "reason": reason, "method": method,
                                   "confidence": confidence},
            "next_node": "semantic_arbiter",
        }

    # 只有一路有答案
    single = reasoning_answer or python_answer
    return {
        "validation_status": "uncertain",
        "validated_answer": single,
        "validation_details": {"problem_type": "computation",
                               "reason": "只有一路有答案"},
        "next_node": "semantic_arbiter",
    }
