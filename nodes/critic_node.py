"""nodes/critic_node.py — 过程审计（定稿前最后一道质量门）。

交叉验证只回答"两路是否一致"，不回答"答案是否覆盖题面全部要求"。
Critic 做两级审计：确定性契约检查（零成本）+ prefill LLM 审计，
查出多问漏答、契约缺项、推导矛盾后产生定向修复提示。
"""

from __future__ import annotations

import json
import re

from config import CONFIG
from utils.answer_matcher import is_placeholder_answer
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, thinking_mode_flag
from utils.prompt_templates import CRITIC_PROMPT, CRITIC_PREFILL


def _bounded(value, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[截断]"


def _detect_derivation_conflict(text: str) -> str:
    """推导矛盾自检：同一变量出现两个不同数值（x=3 后又 x=5）。"""
    assigns = re.findall(r"([a-zA-Z])\s*=\s*(-?\d+(?:\.\d+)?)", text)
    seen = {}
    for var, val in assigns:
        if var in seen and seen[var] != val:
            return f"变量 {var} 出现两个不同值：{seen[var]} 与 {val}"
        seen[var] = val
    return ""


def _parse_critic(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"verdict": "pass", "missing": [], "calc_checks": [], "llm_available": False}
    try:
        data = json.loads(m.group(0))
        return {
            "verdict": data.get("verdict", "pass"),
            "missing": data.get("missing", []),
            "calc_checks": data.get("calc_checks", []),
            "llm_available": True,
        }
    except Exception:
        return {"verdict": "pass", "missing": [], "calc_checks": [], "llm_available": False}


def critic_node(state: dict, config) -> dict:
    trace = list(state.get("critic_trace") or [])
    if not CONFIG.get("enable_critic", True):
        return {"critic_status": "skipped", "next_node": "coordinator"}

    deps = get_deps(config)
    rounds = state.get("critic_rounds", 0)
    question_mode = state.get("question_mode", "computation")

    answer = str(state.get("validated_answer") or "").strip()
    if not answer:
        rr = state.get("reasoning_result") or {}
        answer = str(rr.get("answer") or "").strip()
    if not answer or is_placeholder_answer(answer):
        return {"critic_status": "skipped", "critic_trace": trace,
                "next_node": "coordinator"}

    # 客观题单字母/单值答案，LLM 审计无增量，跳过
    if question_mode in ("choice", "true_false", "fill"):
        return {"critic_status": "pass", "critic_trace": trace,
                "next_node": "coordinator"}

    # 推导矛盾自检（纯正则，零成本）
    process_summary = _bounded(str(state.get("reasoning_raw_response") or ""), 3000)
    conflict = _detect_derivation_conflict(process_summary)

    # prefill LLM 审计
    prompt = CRITIC_PROMPT.format(
        problem=_bounded(state.get("problem", ""), 6000),
        process_summary=_bounded(process_summary, 2500),
        answer=_bounded(answer, 4000))
    llm_verdict = {"verdict": "pass", "missing": [], "calc_checks": [], "llm_available": False}
    try:
        raw = chat_prefilled(
            deps.client, messages=[{"role": "user", "content": prompt}],
            prefix=CRITIC_PREFILL, temperature=0.1, max_tokens=1024,
            logger=deps.logger, time_budget=deps.time_budget,
            expected_call_seconds=25, label="critic_prefill",
            reserve_margin_s=60, thinking_mode=thinking_mode_flag(),
        )
        llm_verdict = _parse_critic(raw)
    except Exception:  # noqa: BLE001 - 审计失败不阻塞出答案
        pass

    verdict = llm_verdict.get("verdict", "pass")
    if conflict and verdict == "pass":
        verdict = "calc_error"

    # 确定性契约检查（多问漏答/置信区间/假设检验/枚举 + 必须术语，零成本）
    from utils.answer_contract import missing_components, missing_required_terms, required_terms
    problem = str(state.get("problem", ""))
    deterministic_missing = missing_components(problem, answer)
    # 必须术语缺失（如牛顿法题必须含 x_{n+1}）也是判分硬伤
    req_terms = required_terms(problem)
    missing_terms = missing_required_terms(answer, req_terms)
    if missing_terms:
        deterministic_missing.extend(f"缺必须术语 {t}" for t in missing_terms)
    if deterministic_missing and verdict == "pass":
        verdict = "incomplete"
        llm_verdict["missing"] = list(deterministic_missing)

    if verdict == "pass":
        return {"critic_status": "pass", "critic_trace": trace,
                "next_node": "coordinator"}

    # 缺口成立：可负担且未超轮次则回调解定点补算
    if rounds < 1 and (deps.time_budget is None or deps.time_budget.can_afford(120)):
        missing = llm_verdict.get("missing", [])
        hint = "审计发现答案可能不完整："
        if missing:
            hint += "漏答" + "、".join(missing)
        if conflict:
            hint += f"；{conflict}"
        hint += "。请补齐缺失项并重新推导。"
        return {
            "critic_status": verdict, "critic_trace": trace,
            "critic_rounds": rounds + 1,
            "reasoning_retry_hint": hint, "python_retry_hint": hint,
            "next_node": "reconciliation",
        }
    return {"critic_status": verdict, "critic_trace": trace,
            "next_node": "coordinator"}
