"""nodes/classifier_node.py — 题型/领域/难度分类。

输出三个关键字段：
  - question_mode：computation/proof/choice/true_false/fill
  - category：数学领域（供 skill 文档加载）
  - difficulty：easy/medium/hard（供预算与 token 分级）

先走零成本关键词规则判断题型，再用 prefill LLM 分类领域与难度。
"""

from __future__ import annotations

import json
import re

from config import CONFIG
from utils.deps import get_deps
from utils.llm_retry import chat_prefilled, thinking_mode_flag
from utils.prompt_templates import CLASSIFICATION_PROMPT, CLASSIFICATION_PREFILL

# 18 个数学领域（与 skills/ 目录对应）
ALL_CATEGORIES = [
    "数学分析", "高等代数", "抽象代数", "概率论", "统计推断", "线性回归",
    "随机过程", "复分析", "常微分方程", "偏微分方程", "泛函分析", "测度积分",
    "拓扑学", "微分几何", "数值分析", "离散数学", "运筹学", "非基础及进阶课程",
]

_PROOF_KEYWORDS = ["证明", "求证", "推导", "论证", "试证", "证明或反驳", "当且仅当", "充要"]
_CHOICE_MARKERS = ["A.", "B.", "C.", "D.", "A、", "B、", "C、", "D、"]


def classify_question_mode(problem: str) -> str:
    """零成本题型分类（关键词规则）。"""
    if any(kw in problem for kw in _PROOF_KEYWORDS):
        return "proof"
    if "判断" in problem and ("对" in problem or "错" in problem or "正确" in problem or "错误" in problem):
        return "true_false"
    if len(re.findall(r"[A-D][.、]", problem)) >= 3 or "选项" in problem:
        return "choice"
    if "___" in problem or "（）" in problem or "____" in problem or "填空" in problem:
        return "fill"
    return "computation"


def _parse_classification(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return {
            "category": data.get("category", ""),
            "question_mode": data.get("question_mode", ""),
            "difficulty": data.get("difficulty", "medium"),
            "confidence": data.get("confidence", 0.0),
        }
    except Exception:
        return {}


def classifier_node(state: dict, config) -> dict:
    deps = get_deps(config)
    problem = state.get("problem", "")

    # 题型先用规则判定（零成本）
    question_mode = classify_question_mode(problem)

    # 领域 + 难度用 prefill LLM 分类
    category = "数学分析"
    difficulty = "medium"
    confidence = 0.0
    try:
        prompt = CLASSIFICATION_PROMPT.format(
            allowed_categories="、".join(ALL_CATEGORIES), problem=problem[:3000])
        raw = chat_prefilled(
            deps.client, messages=[{"role": "user", "content": prompt}],
            prefix=CLASSIFICATION_PREFILL, temperature=0.1,
            max_tokens=CONFIG["max_tokens"]["classifier"],
            logger=deps.logger, time_budget=deps.time_budget,
            expected_call_seconds=10, label="classifier_prefill",
            thinking_mode=thinking_mode_flag(),
        )
        parsed = _parse_classification(raw)
        if parsed.get("category") in ALL_CATEGORIES:
            category = parsed["category"]
        if parsed.get("difficulty") in ("easy", "medium", "hard"):
            difficulty = parsed["difficulty"]
        if parsed.get("question_mode") in ("computation", "proof", "choice", "true_false", "fill"):
            question_mode = parsed["question_mode"]
        confidence = parsed.get("confidence", 0.0)
    except Exception:  # noqa: BLE001 - 分类失败用默认值，不阻塞
        pass

    # 按难度收紧软预算（可选阶段的购买力，不杀进行中调用）
    if deps.time_budget is not None:
        deps.time_budget.apply_difficulty_profile(difficulty)

    return {
        "question_mode": question_mode,
        "category": category,
        "difficulty": difficulty,
        "category_confidence": confidence,
    }
