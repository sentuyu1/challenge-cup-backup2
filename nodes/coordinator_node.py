"""nodes/coordinator_node.py — 最终输出。

汇总推理、验证、仲裁、审计结果，生成 final_response。
判分只认 final_response 里的答案，故：
  - 答案锁定时逐字保留仲裁候选（不改写、不格式化）
  - 计算题收敛为简洁答案（带必要推导）
  - 证明题保留完整推理
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.answer_matcher import is_placeholder_answer
from utils.deps import get_deps
from utils.llm_retry import chat_with_retry, thinking_mode_flag
from utils.prompt_templates import COORDINATOR_PROMPT


def _extract_boxed(text: str) -> str:
    idx = text.find("\\boxed{")
    if idx < 0:
        return ""
    start = idx + len("\\boxed{")
    depth, pos = 1, start
    while pos < len(text) and depth > 0:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    return text[start:pos - 1].strip() if depth == 0 else ""


def _build_deterministic(problem: str, answer: str, question_mode: str) -> str:
    """确定性兜底：不付 LLM 调用，直接拼装 final_response。"""
    if question_mode in ("choice", "true_false", "fill"):
        return answer
    if question_mode == "proof":
        return answer
    boxed = answer if answer.startswith("\\boxed") else f"\\boxed{{{answer}}}"
    return f"{problem}\n\n最终答案：{boxed}"


def coordinator_node(state: dict, config) -> dict:
    deps = get_deps(config)
    problem = state.get("problem", "")
    question_mode = state.get("question_mode", "computation")
    validated_answer = str(state.get("validated_answer") or "").strip()

    # 答案锁定：逐字保留仲裁候选
    if state.get("answer_locked"):
        if validated_answer:
            return {"final_response": validated_answer, "coordination_detail": ""}
        validated_answer = "无法确定答案"

    # answer_frame 渲染（裸数值 → 完整句子，折叠桌判分保护）
    from utils.problem_spec import build_problem_spec
    from utils.answer_render import render_answer
    spec = build_problem_spec(problem)
    if getattr(spec, "answer_frame", "math") == "sentence":
        validated_answer = render_answer(validated_answer, spec.question_kind)

    # 无答案：应急直答
    if not validated_answer or is_placeholder_answer(validated_answer):
        try:
            from utils.prompt_templates import EMERGENCY_PROMPT
            resp = chat_with_retry(
                deps.client,
                messages=[{"role": "user",
                           "content": EMERGENCY_PROMPT.format(problem=problem[:2000])}],
                temperature=0.2, max_tokens=CONFIG["max_tokens"]["emergency_answer"],
                logger=deps.logger, time_budget=deps.time_budget,
                label="emergency_answer", thinking_mode=thinking_mode_flag(),
            )
            return {"final_response": resp, "coordination_detail": resp,
                    "fallback_source": "emergency"}
        except Exception:  # noqa: BLE001
            return {"final_response": "无法确定答案", "coordination_detail": ""}

    # 客观题：简洁答案
    if question_mode in ("choice", "true_false", "fill"):
        return {"final_response": validated_answer, "coordination_detail": validated_answer}

    # 计算/证明题：完整解答整理
    rr = state.get("reasoning_result") or {}
    reasoning_text = str(state.get("reasoning_raw_response") or "")
    if not reasoning_text:
        # 用确定性拼装兜底
        final = _build_deterministic(problem, validated_answer, question_mode)
        return {"final_response": final, "coordination_detail": final}

    # 预算不足时用确定性兜底
    if deps.time_budget and deps.time_budget.fast_path():
        final = _build_deterministic(problem, validated_answer, question_mode)
        return {"final_response": final, "coordination_detail": final}

    # LLM 整理
    try:
        prompt = COORDINATOR_PROMPT.format(
            problem=problem[:4000], question_mode=question_mode,
            category=state.get("category", "数学"),
            reasoning_steps=reasoning_text[:4000],
            python_code=str(state.get("python_code") or "")[:2000],
            python_output=str((state.get("python_output") or {}).get("stdout") or "")[:2000],
            validated_answer=validated_answer)
        final = chat_with_retry(
            deps.client, messages=[{"role": "user", "content": prompt}],
            temperature=CONFIG["temperatures"]["coordinator"],
            max_tokens=CONFIG["max_tokens"]["coordinator"],
            logger=deps.logger, time_budget=deps.time_budget,
            label="coordinator", thinking_mode=thinking_mode_flag(),
        )
        # 确保最终答案字段存在
        if "最终答案" not in final and validated_answer:
            final = final + f"\n\n最终答案：{validated_answer}"
        return {"final_response": final, "coordination_detail": final}
    except Exception:  # noqa: BLE001
        final = _build_deterministic(problem, validated_answer, question_mode)
        return {"final_response": final, "coordination_detail": final}
