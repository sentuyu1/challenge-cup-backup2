"""nodes/reasoning_agent_node.py — LLM 推理路径。

独立生成结构化推理答案。客观题（选择/判断/填空）走短路径，
计算/证明题走四章节完整推理。
"""

from __future__ import annotations

import re

from config import CONFIG
from utils.answer_extractor import parse_reasoning_output
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, chat_with_retry, thinking_mode_flag
from utils.prompt_templates import OBJECTIVE_PROMPT, REASONING_PROMPT


def is_objective_mode(question_mode: str) -> bool:
    return question_mode in ("choice", "true_false", "fill")


def _skill_doc(deps, category: str) -> str:
    loader = getattr(deps, "skills_loader", None)
    if loader is None:
        return ""
    getter = getattr(loader, "get_skill_document", None)
    return getter(category) if callable(getter) else ""


def _objective_answer_shape(question_mode: str) -> str:
    if question_mode == "true_false":
        return "正确 或 错误"
    if question_mode == "fill":
        return "按空位顺序写全部结果，多空用分号分隔"
    return "列出全部正确选项字母"


def reasoning_agent_node(state: dict, config) -> dict:
    deps = get_deps(config)
    client = deps.client
    problem = state.get("problem", "")
    category = state.get("category", "数学")
    question_mode = state.get("question_mode", "computation")
    hint = state.get("branch_hint")

    trace = []
    attempts = 0
    response = ""

    # ── 客观题短路径 ──
    if is_objective_mode(question_mode):
        prompt = OBJECTIVE_PROMPT.format(
            question_mode=question_mode,
            category=category,
            domain_guard="",
            answer_shape=_objective_answer_shape(question_mode),
            problem=problem,
        )
        try:
            attempts = 1
            response = chat_with_retry(
                client, messages=[{"role": "user", "content": prompt}],
                temperature=CONFIG["temperatures"]["objective_reasoning"],
                max_tokens=CONFIG["max_tokens"]["objective_reasoning"],
                logger=deps.logger, time_budget=deps.time_budget,
                expected_call_seconds=45, label="objective_reasoning",
                thinking_mode=thinking_mode_flag(),
            )
        except Exception as exc:  # noqa: BLE001
            trace.append({"attempt": 1, "status": "failed", "error": str(exc)[:200]})
        parsed = parse_reasoning_output(response)
        if not parsed.get("answer"):
            # prefill 重试一次
            try:
                attempts = 2
                response = chat_prefilled(
                    client, messages=[{"role": "user", "content": prompt}],
                    prefix="答案：",
                    temperature=CONFIG["temperatures"]["objective_reasoning"],
                    max_tokens=CONFIG["max_tokens"]["objective_reasoning"],
                    logger=deps.logger, time_budget=deps.time_budget,
                    expected_call_seconds=60, label="objective_reasoning_prefill",
                    thinking_mode=thinking_mode_flag(),
                )
                parsed = parse_reasoning_output(response)
            except Exception as exc:  # noqa: BLE001
                trace.append({"attempt": 2, "status": "failed", "error": str(exc)[:200]})
        return {
            "reasoning_result": parsed,
            "reasoning_raw_response": response,
            "reasoning_trace": trace,
            "reasoning_attempts": attempts,
        }

    # ── 计算/证明题四章节 ──
    skill_doc = _skill_doc(deps, category)
    prompt = REASONING_PROMPT.format(
        category=category, skill_document=skill_doc[:3000], problem=problem)
    if hint:
        prompt += f"\n\n[复核提示] {hint}"

    max_attempts = 1 if (deps.time_budget and deps.time_budget.fast_path()) else CONFIG["llm_max_retries"]
    reasoning_tokens = CONFIG["reasoning_tokens_by_difficulty"].get(
        state.get("difficulty", "medium"), CONFIG["max_tokens"]["reasoning"])

    parsed = {"analysis": "", "steps": [], "answer": "", "validation_points": []}
    for _ in range(max_attempts):
        attempts += 1
        try:
            response = chat_with_retry(
                client, messages=[{"role": "user", "content": prompt}],
                temperature=CONFIG["temperatures"]["reasoning"],
                max_tokens=reasoning_tokens,
                logger=deps.logger, time_budget=deps.time_budget,
                label="reasoning", thinking_mode=thinking_mode_flag(),
            )
        except Exception as exc:  # noqa: BLE001
            trace.append({"attempt": attempts, "status": "failed", "error": str(exc)[:200]})
            break
        parsed = parse_reasoning_output(response)
        if parsed.get("answer") and parsed.get("steps"):
            break
        # 格式缺失时带格式提醒重试一次
        prompt = (REASONING_PROMPT.format(
            category=category, skill_document=skill_doc[:3000], problem=problem)
            + "\n\n注意：上一次输出缺少必需章节。请严格按四章节格式重新输出。")

    return {
        "reasoning_result": parsed,
        "reasoning_raw_response": response,
        "reasoning_trace": trace,
        "reasoning_attempts": attempts,
    }
