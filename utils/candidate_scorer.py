"""utils/candidate_scorer.py — 候选答案打分评估（借鉴折叠桌 candidate_selector）。

对每个候选答案做多维打分，选最优候选，而非简单符号等价二选一。
打分维度：
  - 完整性（覆盖题面全部子目标/必须术语）
  - 形状合法（答案形状匹配题型）
  - 格式合法（无污染/残片/占位符）
  - 工具一致（与 SymPy 计算一致）
  - 显式答案（有明确答案标记）
"""

from __future__ import annotations

import re

from utils.answer_cleanliness import (
    clean_answer, is_noise_answer, is_placeholder_answer,
    looks_incomplete_answer, looks_like_latex_fragment)
from utils.answer_contract import missing_components, missing_required_terms, required_terms


def _compact(value: str) -> str:
    return re.sub(r"[\s{}()\[\]\\,，。；;：:_]", "", str(value or "").lower()).replace("−", "-")


def assess_answer(answer: str, problem: str, question_mode: str, tool_answer: str = "") -> dict:
    """评估单个候选答案，返回打分详情。"""
    value = (answer or "").strip()
    score = 0
    reasons = []

    # 1. 非空且非占位
    if not value or is_placeholder_answer(value) or is_noise_answer(value):
        return {"answer": value, "score": -50, "complete": False, "shape_valid": False,
                "format_valid": False, "reasons": ["空/占位/噪声"]}

    # 2. 格式合法（20 种结构校验：残片/未闭合/控制字符/markup/元叙述）
    from utils.answer_cleanliness import validate_structure
    structure_reasons = validate_structure(value)
    format_valid = not structure_reasons
    if format_valid:
        score += 4
    else:
        score -= 12
        reasons.extend(structure_reasons)

    # 3. 完整性（覆盖必须术语 + 可判分要求 + 契约）
    from utils.problem_spec import build_problem_spec
    spec = build_problem_spec(problem)
    missing_terms = missing_required_terms(value, spec.required_terms)
    missing_reqs = [r.name for r in spec.requirements if r.strict and not r.matches(value)]
    missing_comp = missing_components(problem, value)
    complete = not missing_terms and not missing_reqs and not missing_comp
    if complete:
        score += 8
    else:
        score -= 8
        reasons.extend(f"缺:{t}" for t in missing_terms + missing_reqs + missing_comp)

    # 4. 形状合法（判断题硬性校验；计数/概率/年龄的单位只做软提示，不排除候选）
    shape_valid = True
    frame = spec.answer_frame
    kind = spec.question_kind
    if frame == "sentence":
        if kind == "truth" and not re.search(r"是|否|正确|错误|成立|不成立|收敛|发散", value):
            # 判断题必须有明确判断词（判分硬性要求）
            shape_valid = False
            reasons.append("判断题无明确判断")
        elif kind == "count" and re.search(r"共|有|答案", value) and not re.search(r"个|种|项|条", value):
            # 仅当答案写成句子却漏了单位时才提示，纯数字不扣
            reasons.append("计数句缺单位")
        elif kind == "probability" and re.search(r"概率|probability", value) and "概率" not in value:
            reasons.append("概率句缺'概率'")
    elif question_mode == "true_false" and not re.search(r"正确|错误|是|否", value):
        shape_valid = False
        reasons.append("判断题无明确判断")
    if shape_valid:
        score += 4
    else:
        score -= 4

    # 5. 工具一致（与 SymPy 计算一致，确定性结果加分）
    if tool_answer:
        tool_compact = _compact(tool_answer)
        if tool_compact and tool_compact in _compact(value):
            score += 4

    return {"answer": value, "score": score, "complete": complete,
            "shape_valid": shape_valid, "format_valid": format_valid,
            "reasons": reasons, "missing": missing_terms + missing_comp}


def choose_best(assessments: list, tool_answer: str = "") -> str:
    """从多个候选评估中选最优答案。"""
    usable = [a for a in assessments if a["format_valid"] and a["shape_valid"] and a["score"] >= 0]
    if not usable:
        usable = assessments
    if not usable:
        return ""

    best = max(usable, key=lambda a: (
        a["complete"], a["score"], a["format_valid"], a["shape_valid"],
        len(a["answer"])))
    return best["answer"]
