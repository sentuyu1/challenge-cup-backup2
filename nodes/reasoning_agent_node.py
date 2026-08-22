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


def _build_goal_context(spec) -> str:
    """生成目标清单 + 风险提示（折叠桌式，避免指令被模型复述）。"""
    rendered = []
    for goal in getattr(spec, "goals", []):
        rendered.append(f"- 目标：{str(goal)[:200]}")
    # 必查字段（ProblemSpec 级别的可判分要求）
    req_names = "、".join(r.name for r in getattr(spec, "requirements", []))
    if req_names:
        rendered.append(f"- 必查字段：{req_names}")
    # 风险提示（把 risk_flags 转成针对性口径提醒，不用指令式"不要只写数值"）
    risk_notes = {
        "endpoint_error": "注意端点是否可达（由 ≤ 推出的界在严格不等号下取不到）",
        "missing_roots": "注意列出全部根并检查定义域",
        "double_counting": "计数时注意对称因子只乘一次、序号从 1 起数",
        "multiple_goals": "注意逐问回答，不要漏答",
        "modular_structure": "注意在模结构中运算（如 F_2 内求和要取模）",
    }
    for flag in getattr(spec, "risk_flags", []):
        note = risk_notes.get(flag)
        if note:
            rendered.append(f"- 注意：{note}")
    return "\n".join(rendered) if rendered else "- 直接求解并给出完整结论"


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

    # ── 计算/证明题：完整复现折叠桌（sympy 证据 + 多候选 + verifier 选优补全）──
    from utils.problem_spec import build_problem_spec
    from utils.sympy_hints import hints_for
    spec = build_problem_spec(problem)
    goal_context = _build_goal_context(spec)
    sympy_hints = hints_for(problem)
    hint_text = "\n".join(f"- {h}" for h in sympy_hints) if sympy_hints else ""
    base_prompt = REASONING_PROMPT.format(
        category=category, goal_context=goal_context, problem=problem)
    if hint_text:
        base_prompt += f"\n本地计算证据（已算好，可直接采用）：\n{hint_text}"
    if hint:
        base_prompt += f"\n\n[复核提示] {hint}"

    difficulty = state.get("difficulty", "medium")
    reasoning_tokens = CONFIG["reasoning_tokens_by_difficulty"].get(
        difficulty, CONFIG["max_tokens"]["reasoning"])

    # 多候选（hard 3 候选，温度梯度增加多样性）
    candidate_count = 3 if difficulty == "hard" else 1
    temperatures = [0.2, 0.35, 0.5] if candidate_count > 1 else [CONFIG["temperatures"]["reasoning"]]

    trace = []
    attempts = 0
    candidates = []  # [(parsed, response)]

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
        if parsed.get("answer"):
            candidates.append((parsed, response))

    # verifier：多候选 + 丰富上下文，独立重算选优补全（折叠桌核心）
    if not candidates:
        parsed = {"analysis": "", "steps": [], "answer": "", "validation_points": []}
        raw_response = ""
    elif len(candidates) == 1:
        parsed, raw_response = candidates[0]
    else:
        attempts += 1
        parsed, raw_response = _verify_select(
            problem, candidates, sympy_hints, goal_context, client, deps, trace, attempts)

    return {
        "reasoning_result": parsed,
        "reasoning_raw_response": raw_response,
        "reasoning_trace": trace,
        "reasoning_attempts": attempts,
    }


def _verify_select(problem, candidates, sympy_hints, goal_context, client, deps, trace, attempt_no):
    """折叠桌式 verifier：多候选 + 丰富上下文，独立重算选优补全。"""
    joined = "\n\n".join(
        f"候选{i + 1}：{c[0].get('answer', '')[:1500]}" for i, c in enumerate(candidates))
    hint_text = "\n".join(f"- {h}" for h in sympy_hints) if sympy_hints else ""
    verify_prompt = (
        "你是中文数学解答验证器和最终答复编辑器。根据题目和候选答案，独立检查计算、条件、证明逻辑以及是否完整回答。\n\n"
        f"题目：\n{problem}\n\n"
        f"目标清单：\n{goal_context}\n\n"
        f"候选答案：\n{joined}\n"
    )
    if hint_text:
        verify_prompt += f"\n本地计算证据：\n{hint_text}\n"
    verify_prompt += (
        "\n请独立重新计算，检查候选是否正确完整，补全所有对象/数值/结论。只输出一行：\n"
        "FINAL: <完整正确答案>"
    )
    try:
        verify_response = chat_with_retry(
            client, messages=[{"role": "user", "content": verify_prompt}],
            temperature=0.2, max_tokens=2048,
            logger=deps.logger, time_budget=deps.time_budget,
            label="verify", thinking_mode=thinking_mode_flag(),
        )
    except Exception as exc:  # noqa: BLE001
        trace.append({"attempt": attempt_no, "status": "failed", "error": str(exc)[:200]})
        return candidates[0]
    final_ans = _extract_verify_final(verify_response)
    parsed, raw = candidates[0]
    if final_ans:
        parsed = dict(parsed)
        parsed["answer"] = final_ans
        parsed["answer_source"] = "verified"
        raw = verify_response
    return parsed, raw


def _extract_verify_final(text: str) -> str:
    """从 verifier 输出提取 FINAL: xxx。"""
    m = re.search(r"FINAL\s*[:：]\s*(.+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else ""


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
