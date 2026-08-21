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


_knowledge_cards_cache = None


def _get_knowledge_cards():
    """知识卡片检索器（模块级缓存，避免每题重复加载 31 个 txt）。"""
    global _knowledge_cards_cache
    if _knowledge_cards_cache is None:
        from utils.knowledge_cards import KnowledgeCards
        _knowledge_cards_cache = KnowledgeCards()
    return _knowledge_cards_cache


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

    # ── 计算/证明题四章节（hard 题多候选 + 共识选择）──
    skill_doc = _skill_doc(deps, category)
    from utils.skill_excerpt import select_skill_excerpt
    skill_excerpt = select_skill_excerpt(skill_doc, problem, 3000)
    # 知识卡片（方法+检查清单+领域知识，缓存避免重复加载）
    cards = _get_knowledge_cards().retrieve(problem, category)
    skill_context = skill_excerpt + ("\n\n知识卡片（解题要点）：\n" + cards if cards else "")
    base_prompt = REASONING_PROMPT.format(
        category=category, skill_document=skill_context, problem=problem)
    if hint:
        base_prompt += f"\n\n[复核提示] {hint}"

    difficulty = state.get("difficulty", "medium")
    reasoning_tokens = CONFIG["reasoning_tokens_by_difficulty"].get(
        difficulty, CONFIG["max_tokens"]["reasoning"])

    # hard 题生成 3 候选（温度梯度），easy/medium 单候选
    candidate_count = 3 if difficulty == "hard" else 1
    temperatures = [0.2, 0.5, 0.8] if candidate_count > 1 else [CONFIG["temperatures"]["reasoning"]]

    candidates = []
    trace = []
    attempts = 0
    for cid in range(candidate_count):
        attempts += 1
        try:
            response = chat_with_retry(
                client, messages=[{"role": "user", "content": base_prompt}],
                temperature=temperatures[cid] if cid < len(temperatures) else 0.5,
                max_tokens=reasoning_tokens,
                logger=deps.logger, time_budget=deps.time_budget,
                label=f"reasoning_{cid}", thinking_mode=thinking_mode_flag(),
            )
        except Exception as exc:  # noqa: BLE001
            trace.append({"attempt": attempts, "status": "failed", "error": str(exc)[:200]})
            break
        parsed = parse_reasoning_output(response)
        if parsed.get("answer") and parsed.get("steps"):
            candidates.append(parsed)
        elif parsed.get("answer"):
            # 有答案但缺步骤：保留答案（可能格式不完整）
            candidates.append(parsed)

    # 共识选择：多候选时按答案等价找多数
    parsed = _select_consensus(candidates)
    if not candidates:
        parsed = {"analysis": "", "steps": [], "answer": "", "validation_points": []}

    return {
        "reasoning_result": parsed,
        "reasoning_raw_response": candidates[0].get("answer", "") if candidates else "",
        "reasoning_trace": trace,
        "reasoning_attempts": attempts,
    }


def _select_consensus(candidates):
    """多候选按答案等价找多数共识，返回票数最高的候选。"""
    if not candidates:
        return {"analysis": "", "steps": [], "answer": "", "validation_points": []}
    if len(candidates) == 1:
        return candidates[0]
    from utils.answer_matcher import match_computation

    groups = []  # [(代表答案, [候选...])]
    for c in candidates:
        ans = c.get("answer", "")
        if not ans:
            continue
        matched = False
        for rep, group in groups:
            is_match, conf, _, _ = match_computation(rep, ans)
            if is_match and conf >= 0.8:
                group.append(c)
                matched = True
                break
        if not matched:
            groups.append((ans, [c]))
    if not groups:
        return candidates[0]
    # 选票数最多、且答案最完整（含步骤）的组
    best = max(groups, key=lambda g: (len(g[1]), any(c.get("steps") for c in g[1])))
    best_candidates = best[1]
    # 组内选步骤最完整的
    return max(best_candidates, key=lambda c: len(c.get("steps", [])))
